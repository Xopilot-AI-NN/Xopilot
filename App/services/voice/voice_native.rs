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
    automatic: bool,
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
    let mut gate = super::voice::SilenceGate::default();
    let mut observed = 0;
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
        if automatic {
            let samples = samples.lock().map_err(|_| {
                anyhow::anyhow!("Ошибка микрофона")
            })?;
            let fresh = &samples[observed..];
            if !fresh.is_empty() {
                let rms = (fresh
                    .iter()
                    .map(|v| v * v)
                    .sum::<f32>()
                    / fresh.len() as f32)
                    .sqrt();
                let seconds =
                    fresh.len() as f32 / rate as f32;
                observed = samples.len();
                if gate.update(rms, seconds) {
                    break;
                }
            }
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
    ensure!(
        !automatic || gate.heard,
        "Речь не обнаружена. Нажмите Live и попробуйте ещё раз"
    );
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

/// Интерполирую mono и дублирую отсчёт по выходным каналам без отдельного буфера.
fn fill_output<T: cpal::Sample + cpal::FromSample<f32>>(
    output: &mut [T],
    samples: &[f32],
    start: usize,
    channels: usize,
    ratio: f64,
) -> usize {
    for (offset, frame) in
        output.chunks_mut(channels).enumerate()
    {
        let at = (start + offset) as f64 * ratio;
        let index = at as usize;
        let fraction = (at - index as f64) as f32;
        let left =
            samples.get(index).copied().unwrap_or(0.);
        let right =
            samples.get(index + 1).copied().unwrap_or(0.);
        let value = left + (right - left) * fraction;
        frame.fill(T::from_sample_(value.clamp(-1., 1.)));
    }
    output.len() / channels
}

/// Вывожу PCM через ALSA, поток закрывается сразу после отмены или конца фразы.
pub(super) fn play(
    samples: Vec<f32>,
    rate: u32,
    stop: CancellationToken,
) -> Result<()> {
    use std::sync::atomic::{AtomicUsize, Ordering};
    ensure!(!samples.is_empty() && rate > 0, "Пустой звук");
    let device = cpal::default_host()
        .default_output_device()
        .context("Устройство вывода звука не найдено")?;
    let config = device.default_output_config()?;
    let format = config.sample_format();
    ensure!(
        matches!(
            format,
            cpal::SampleFormat::F32
                | cpal::SampleFormat::F64
                | cpal::SampleFormat::I16
                | cpal::SampleFormat::U16
                | cpal::SampleFormat::I32
        ),
        "Неподдерживаемый формат вывода звука"
    );
    let output_rate = config.sample_rate();
    let channels = usize::from(config.channels());
    ensure!(
        output_rate > 0 && channels > 0,
        "Неверные параметры вывода звука"
    );
    let frames = (samples.len() as u64
        * u64::from(output_rate)
        / u64::from(rate)) as usize;
    let cursor = Arc::new(AtomicUsize::new(0));
    let position = cursor.clone();
    let failure = Arc::new(Mutex::new(None));
    let callback_failure = failure.clone();
    let ratio = f64::from(rate) / f64::from(output_rate);
    let stream = device.build_output_stream_raw(
        config.config(),
        format,
        move |data, _| {
            let start = position.load(Ordering::Relaxed);
            let frames = match format {
                cpal::SampleFormat::F32 => data
                    .as_slice_mut::<f32>()
                    .map(|output| {
                        fill_output(
                            output, &samples, start,
                            channels, ratio,
                        )
                    })
                    .unwrap_or(0),
                cpal::SampleFormat::F64 => data
                    .as_slice_mut::<f64>()
                    .map(|output| {
                        fill_output(
                            output, &samples, start,
                            channels, ratio,
                        )
                    })
                    .unwrap_or(0),
                cpal::SampleFormat::I16 => data
                    .as_slice_mut::<i16>()
                    .map(|output| {
                        fill_output(
                            output, &samples, start,
                            channels, ratio,
                        )
                    })
                    .unwrap_or(0),
                cpal::SampleFormat::U16 => data
                    .as_slice_mut::<u16>()
                    .map(|output| {
                        fill_output(
                            output, &samples, start,
                            channels, ratio,
                        )
                    })
                    .unwrap_or(0),
                cpal::SampleFormat::I32 => data
                    .as_slice_mut::<i32>()
                    .map(|output| {
                        fill_output(
                            output, &samples, start,
                            channels, ratio,
                        )
                    })
                    .unwrap_or(0),
                _ => 0,
            };
            position.fetch_add(frames, Ordering::Relaxed);
        },
        move |error| {
            if let Ok(mut value) = callback_failure.lock() {
                *value = Some(error.to_string());
            }
        },
        Some(Duration::from_secs(5)),
    )?;
    stream.play()?;
    let began = Instant::now();
    while !stop.is_cancelled()
        && cursor.load(Ordering::Relaxed) < frames
    {
        if failure.lock().unwrap().is_some() {
            break;
        }
        ensure!(
            began.elapsed().as_secs_f64()
                < frames as f64 / f64::from(output_rate)
                    + 5.,
            "Устройство звука не отвечает"
        );
        std::thread::sleep(Duration::from_millis(10));
    }
    if !stop.is_cancelled() {
        std::thread::sleep(Duration::from_millis(120));
    }
    drop(stream);
    if let Some(error) = failure.lock().unwrap().take() {
        anyhow::bail!("Ошибка звука: {error}");
    }
    ensure!(
        !stop.is_cancelled(),
        "Озвучивание остановлено"
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    /// Проверяю дублирование каналов, промежуточный отсчёт и тишину после конца.
    #[test]
    fn output_interpolates_mono_and_fills_end_with_silence()
    {
        let mut output = [0f32; 8];
        assert_eq!(
            super::fill_output(
                &mut output,
                &[1., 0.],
                0,
                2,
                0.5
            ),
            4
        );
        assert_eq!(
            output,
            [1., 1., 0.5, 0.5, 0., 0., 0., 0.]
        );
        let mut integer = [0i16; 2];
        super::fill_output(
            &mut integer,
            &[-2., 2.],
            0,
            1,
            1.,
        );
        assert_eq!(integer, [i16::MIN, i16::MAX]);
    }

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
