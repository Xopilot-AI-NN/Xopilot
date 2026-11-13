// Описание: Нативный захват Linux/ALSA в worker без кодеков WebView.
use anyhow::{Context, Result, ensure};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::{
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
use tokio_util::sync::CancellationToken;

/// Смешивает входные каналы с проверкой общего лимита записи.
fn append<T: cpal::Sample>(
    input: &[T],
    channels: usize,
    limit: usize,
    output: &mut Vec<f32>,
) where
    f32: cpal::FromSample<T>,
{
    let available = limit.saturating_sub(output.len());
    output.extend(
        input.chunks_exact(channels).take(available).map(
            |frame| {
                frame
                    .iter()
                    .map(|sample| sample.to_sample::<f32>())
                    .sum::<f32>()
                    / channels as f32
            },
        ),
    );
}

/// Владеет потоком до остановки или 30 секунд. Drop закрывает устройство
/// до подготовки WAV и обращения к модели.
pub(super) fn record(
    stop: CancellationToken,
) -> Result<Vec<u8>> {
    let device = cpal::default_host()
        .default_input_device()
        .context("Микрофон не найден")?;
    let config = device.default_input_config()?;
    let rate = config.sample_rate();
    let channels = usize::from(config.channels());
    let format = config.sample_format();
    ensure!(
        rate > 0
            && rate <= 192000
            && (1..=8).contains(&channels),
        "Неподдерживаемые параметры микрофона"
    );
    ensure!(
        matches!(
            format,
            cpal::SampleFormat::F32
                | cpal::SampleFormat::F64
                | cpal::SampleFormat::I16
                | cpal::SampleFormat::U16
                | cpal::SampleFormat::I32
        ),
        "Формат микрофона не поддерживается"
    );
    let limit = rate as usize * 30;
    let samples =
        Arc::new(Mutex::new(Vec::with_capacity(limit)));
    let target = samples.clone();
    let failure = Arc::new(Mutex::new(None));
    let callback_failure = failure.clone();
    let stream = device.build_input_stream_raw(
        config.config(),
        format,
        move |data, _| {
            let Ok(mut output) = target.lock() else {
                return;
            };
            match format {
                cpal::SampleFormat::F32 => {
                    if let Some(input) =
                        data.as_slice::<f32>()
                    {
                        append(
                            input,
                            channels,
                            limit,
                            &mut output,
                        );
                    }
                }
                cpal::SampleFormat::F64 => {
                    if let Some(input) =
                        data.as_slice::<f64>()
                    {
                        append(
                            input,
                            channels,
                            limit,
                            &mut output,
                        );
                    }
                }
                cpal::SampleFormat::I16 => {
                    if let Some(input) =
                        data.as_slice::<i16>()
                    {
                        append(
                            input,
                            channels,
                            limit,
                            &mut output,
                        );
                    }
                }
                cpal::SampleFormat::U16 => {
                    if let Some(input) =
                        data.as_slice::<u16>()
                    {
                        append(
                            input,
                            channels,
                            limit,
                            &mut output,
                        );
                    }
                }
                cpal::SampleFormat::I32 => {
                    if let Some(input) =
                        data.as_slice::<i32>()
                    {
                        append(
                            input,
                            channels,
                            limit,
                            &mut output,
                        );
                    }
                }
                _ => {}
            }
        },
        move |error| {
            if let Ok(mut failure) = callback_failure.lock()
            {
                *failure = Some(error.to_string());
            }
        },
        Some(Duration::from_secs(5)),
    )?;
    stream.play()?;
    let began = Instant::now();
    while !stop.is_cancelled()
        && began.elapsed() < Duration::from_secs(30)
    {
        if samples
            .lock()
            .map_err(|_| {
                anyhow::anyhow!("Ошибка буфера микрофона")
            })?
            .len()
            >= limit
        {
            break;
        }
        if failure
            .lock()
            .map_err(|_| {
                anyhow::anyhow!("Ошибка микрофона")
            })?
            .is_some()
        {
            break;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    drop(stream);
    if let Some(error) = failure.lock().unwrap().take() {
        anyhow::bail!("Ошибка микрофона: {error}");
    }
    let samples = samples.lock().map_err(|_| {
        anyhow::anyhow!("Ошибка буфера микрофона")
    })?;
    ensure!(
        samples.len() >= rate as usize * 15 / 100,
        "Запись слишком короткая"
    );
    let bytes = super::media_codecs::wav(&samples, rate);
    super::media::validate_wav(&bytes)?;
    Ok(bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn input_is_downmixed_and_bounded() {
        let mut output = Vec::new();
        append(
            &[0.5_f32, -0.5, 0.2, 0.4, 1.0, 1.0],
            2,
            2,
            &mut output,
        );
        assert_eq!(output.len(), 2);
        assert_eq!(output[0], 0.0);
        assert!((output[1] - 0.3).abs() < 0.001);
        append(&[i16::MAX, i16::MAX], 2, 2, &mut output);
        assert_eq!(output.len(), 2);
    }
}
