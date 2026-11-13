// Описание: Встроенные декодеры звука и MP4/H.264. Плагины WebView не нужны.
// Внешние процессы не запускаются. Данные декодируются в ограниченном worker.
use super::media::{Frame, Prepared};
use anyhow::{Context, Result, bail, ensure};
use base64::{Engine as _, prelude::BASE64_STANDARD};
use std::{
    io::{Cursor, ErrorKind},
    path::Path,
};
use symphonia::core::{
    audio::SampleBuffer,
    codecs::DecoderOptions,
    errors::Error,
    formats::FormatOptions,
    io::{MediaSourceStream, MediaSourceStreamOptions},
    meta::MetadataOptions,
    probe::Hint,
};
use tokio_util::sync::CancellationToken;

/// Ограничение длительности не требует повторного полного декодирования
/// другим движком, которое могло бы выделить память для многочасового файла.
#[derive(Debug)]
pub(super) struct DurationLimit;
impl std::fmt::Display for DurationLimit {
    fn fmt(
        &self,
        formatter: &mut std::fmt::Formatter<'_>,
    ) -> std::fmt::Result {
        formatter.write_str("Для анализа выберите медиа длительностью до 30 секунд")
    }
}
impl std::error::Error for DurationLimit {}

/// Декодирует аудиодорожку в mono f32. Поток ограничен 30 секундами,
/// изменение частоты и числа каналов внутри файла считается ошибкой.
fn samples(
    bytes: &[u8],
    extension: &str,
    token: &CancellationToken,
) -> Result<(Vec<f32>, u32)> {
    let source = MediaSourceStream::new(
        Box::new(Cursor::new(bytes.to_vec())),
        MediaSourceStreamOptions::default(),
    );
    let mut hint = Hint::new();
    hint.with_extension(extension);
    let mut format = symphonia::default::get_probe()
        .format(
            &hint,
            source,
            &FormatOptions::default(),
            &MetadataOptions::default(),
        )?
        .format;
    let track = format
        .tracks()
        .iter()
        .find(|track| {
            track.codec_params.sample_rate.is_some()
        })
        .context("Нет доступной аудиодорожки")?;
    let id = track.id;
    let mut decoder = symphonia::default::get_codecs()
        .make(
            &track.codec_params,
            &DecoderOptions::default(),
        )?;
    let mut mono = Vec::new();
    let mut rate = 0;
    loop {
        ensure!(
            !token.is_cancelled(),
            "Подготовка медиа отменена"
        );
        let packet = match format.next_packet() {
            Ok(packet) => packet,
            Err(Error::IoError(error))
                if error.kind()
                    == ErrorKind::UnexpectedEof =>
            {
                break;
            }
            Err(error) => return Err(error.into()),
        };
        if packet.track_id() != id {
            continue;
        }
        let decoded = decoder.decode(&packet)?;
        let spec = *decoded.spec();
        let channels = spec.channels.count();
        ensure!(
            (1..=8).contains(&channels)
                && spec.rate > 0
                && spec.rate <= 192000,
            "Неподдерживаемые параметры звука"
        );
        if rate == 0 {
            rate = spec.rate;
        }
        ensure!(
            rate == spec.rate,
            "Частота аудио изменилась внутри файла"
        );
        let mut buffer = SampleBuffer::<f32>::new(
            decoded.capacity() as u64,
            spec,
        );
        buffer.copy_interleaved_ref(decoded);
        mono.extend(
            buffer.samples().chunks_exact(channels).map(
                |frame| {
                    frame.iter().sum::<f32>()
                        / channels as f32
                },
            ),
        );
        ensure!(
            mono.len() <= rate as usize * 30,
            DurationLimit
        );
    }
    ensure!(!mono.is_empty(), "В аудиодорожке нет звука");
    Ok((mono, rate))
}

/// Пересчитывает частоту до 16 кГц и создаёт фиксированный WAV PCM16.
fn wav(samples: &[f32], rate: u32) -> Vec<u8> {
    let count = (samples.len() as u64 * 16000 / rate as u64)
        as usize;
    let size = count * 2;
    let mut bytes = Vec::with_capacity(44 + size);
    bytes.extend_from_slice(b"RIFF");
    bytes.extend_from_slice(
        &(36 + size as u32).to_le_bytes(),
    );
    bytes.extend_from_slice(b"WAVEfmt ");
    bytes.extend_from_slice(&16_u32.to_le_bytes());
    bytes.extend_from_slice(&1_u16.to_le_bytes());
    bytes.extend_from_slice(&1_u16.to_le_bytes());
    bytes.extend_from_slice(&16000_u32.to_le_bytes());
    bytes.extend_from_slice(&32000_u32.to_le_bytes());
    bytes.extend_from_slice(&2_u16.to_le_bytes());
    bytes.extend_from_slice(&16_u16.to_le_bytes());
    bytes.extend_from_slice(b"data");
    bytes.extend_from_slice(&(size as u32).to_le_bytes());
    for index in 0..count {
        let position = index as f64 * rate as f64 / 16000.0;
        let left = position.floor() as usize;
        let fraction = (position - left as f64) as f32;
        let sample = samples[left] * (1.0 - fraction)
            + samples[(left + 1).min(samples.len() - 1)]
                * fraction;
        let sample = if sample.is_finite() {
            sample.clamp(-1.0, 1.0)
        } else {
            0.0
        };
        bytes.extend_from_slice(
            &((sample * 32767.0) as i16).to_le_bytes(),
        );
    }
    bytes
}

/// Превращает AVCC length-prefixed NAL в Annex B для встроенного декодера.
fn annex_b(bytes: &[u8], prefix: usize) -> Result<Vec<u8>> {
    let mut output = Vec::with_capacity(bytes.len() + 32);
    let mut offset = 0;
    while offset < bytes.len() {
        ensure!(
            offset + prefix <= bytes.len(),
            "Оборван размер NAL"
        );
        let mut length = 0_usize;
        for byte in &bytes[offset..offset + prefix] {
            length = (length << 8) | usize::from(*byte);
        }
        offset += prefix;
        ensure!(
            length > 0 && length <= bytes.len() - offset,
            "Оборван NAL видео"
        );
        output.extend_from_slice(&[0, 0, 0, 1]);
        output.extend_from_slice(
            &bytes[offset..offset + length],
        );
        offset += length;
    }
    Ok(output)
}

/// Кодирует только выбранный кадр, уменьшая его до 1024 пикселей по стороне.
fn frame(
    image: &openh264::decoder::DecodedYUV<'_>,
    seconds: f64,
    rotation: u16,
) -> Result<Frame> {
    use openh264::formats::YUVSource;
    let (width, height) = image.dimensions();
    ensure!(
        width > 0
            && height > 0
            && width <= 4096
            && height <= 4096,
        "Размер кадра превышает 4096×4096"
    );
    let mut rgb = vec![0; width * height * 3];
    image.write_rgb8(&mut rgb);
    let image = image::RgbImage::from_raw(
        width as u32,
        height as u32,
        rgb,
    )
    .context("Некорректный видеокадр")?;
    let image = image::DynamicImage::ImageRgb8(image);
    let image = match rotation {
        90 => image.rotate90(),
        180 => image.rotate180(),
        270 => image.rotate270(),
        _ => image,
    };
    let image =
        if image.width() > 1024 || image.height() > 1024 {
            image.thumbnail(1024, 1024)
        } else {
            image
        };
    let mut bytes = Vec::new();
    image::codecs::jpeg::JpegEncoder::new_with_quality(
        &mut bytes, 80,
    )
    .encode_image(&image)?;
    Ok(Frame {
        seconds,
        data: BASE64_STANDARD.encode(bytes),
    })
}

/// Читает MP4/H.264 и выбирает до четырёх кадров. Аудиодорожка обрабатывается
/// отдельно, отсутствие звука не мешает анализу кадров немого видео.
fn video(
    bytes: &[u8],
    token: &CancellationToken,
) -> Result<(Vec<Frame>, f64)> {
    let mut reader = mp4::Mp4Reader::read_header(
        Cursor::new(bytes),
        bytes.len() as u64,
    )?;
    let track = reader
        .tracks()
        .values()
        .find(|track| {
            track.trak.mdia.minf.stbl.stsd.avc1.is_some()
        })
        .context("Нужен MP4 с видео H.264")?;
    let duration = track.duration().as_secs_f64();
    ensure!(
        duration > 0.0 && duration <= 30.0,
        DurationLimit
    );
    ensure!(
        track.width() <= 4096
            && track.height() <= 4096
            && track.sample_count() <= 4000,
        "Видео слишком велико для локального анализа"
    );
    // У видео с телефона поворот часто хранится в матрице дорожки,
    // а не в самих пикселях. Учитываем стандартные четверть-обороты.
    let matrix = &track.trak.tkhd.matrix;
    let rotation =
        match (matrix.a, matrix.b, matrix.c, matrix.d) {
            (0, 65536, -65536, 0) => 90,
            (-65536, 0, 0, -65536) => 180,
            (0, -65536, 65536, 0) => 270,
            _ => 0,
        };
    let id = track.trak.tkhd.track_id;
    let timescale = track.timescale();
    ensure!(
        timescale > 0,
        "Неверная временная шкала видео"
    );
    let count = track.sample_count();
    let config = &track
        .trak
        .mdia
        .minf
        .stbl
        .stsd
        .avc1
        .as_ref()
        .unwrap()
        .avcc;
    let prefix =
        usize::from(config.length_size_minus_one & 3) + 1;
    let mut header = Vec::new();
    for unit in config
        .sequence_parameter_sets
        .iter()
        .chain(&config.picture_parameter_sets)
    {
        header.extend_from_slice(&[0, 0, 0, 1]);
        header.extend_from_slice(&unit.bytes);
    }
    let mut decoder =
        openh264::decoder::Decoder::with_api_config(
            openh264::OpenH264API::from_source(),
            openh264::decoder::DecoderConfig::new()
                .flush_after_decode(
                    openh264::decoder::Flush::NoFlush,
                ),
        )?;
    // MP4 хранит пакеты в порядке декодирования. Для B-кадров временные
    // отметки показа отличаются, поэтому сопоставляем выход с отсортированными PTS.
    let mut times = Vec::with_capacity(count as usize);
    for index in 1..=count {
        let sample = reader
            .read_sample(id, index)?
            .context("Отсутствует видеокадр")?;
        times.push(
            (sample.start_time as f64
                + sample.rendering_offset as f64)
                / timescale as f64,
        );
    }
    times.sort_by(f64::total_cmp);
    let origin = times.first().copied().unwrap_or(0.0);
    let mut displayed = 0;
    let mut frames = Vec::new();
    let mut capture = |image: &openh264::decoder::DecodedYUV<'_>| -> Result<()> {
        let timestamp = times.get(displayed).copied().unwrap_or(duration);
        let seconds = (timestamp - origin).clamp(0.0, duration);
        displayed += 1;
        if frames.len() < 4 && seconds >= frames.len() as f64 * duration / 4.0 {
            frames.push(frame(image, seconds, rotation)?);
        }
        Ok(())
    };
    for index in 1..=count {
        ensure!(
            !token.is_cancelled(),
            "Подготовка медиа отменена"
        );
        let sample = reader
            .read_sample(id, index)?
            .context("Отсутствует видеокадр")?;
        let mut packet = if index == 1 {
            header.clone()
        } else {
            Vec::new()
        };
        packet.extend(annex_b(&sample.bytes, prefix)?);
        let image = decoder.decode(&packet).with_context(|| {
            format!("Ошибка декодирования кадра {index}/{count} ({} байт)", packet.len())
        })?;
        if let Some(image) = image {
            capture(&image)?;
        }
    }
    // Короткий ролик может целиком остаться в буфере переупорядочивания.
    // Завершаем поток после последнего пакета, не сбрасывая ссылки между кадрами.
    for image in decoder.flush_remaining()? {
        capture(&image)?;
    }
    frames.sort_by(|a, b| a.seconds.total_cmp(&b.seconds));
    ensure!(
        !frames.is_empty(),
        "Не удалось декодировать кадры MP4"
    );
    Ok((frames, duration))
}

/// Возвращает результат встроенного декодера; неподдерживаемые контейнеры
/// обрабатываются следующим доступным системным декодером WebView.
pub(super) fn prepare(
    path: &Path,
    bytes: &[u8],
    is_video: bool,
    token: &CancellationToken,
) -> Result<Prepared> {
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("");
    let mut result = Prepared {
        duration: 0.0,
        frames: Vec::new(),
        audio: None,
        warning: String::new(),
    };
    if is_video {
        let (frames, duration) = video(bytes, token)?;
        result.frames = frames;
        result.duration = duration;
    }
    match samples(bytes, extension, token) {
        Ok((samples, rate)) => {
            result.duration = result
                .duration
                .max(samples.len() as f64 / rate as f64);
            result.audio = Some(
                BASE64_STANDARD.encode(wav(&samples, rate)),
            );
        }
        Err(error) if is_video => {
            result.warning = format!(
                "Аудиодорожка недоступна: {error}. Анализируются выбранные кадры."
            )
        }
        Err(error) => bail!(error),
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[ignore = "Нужен XOPILOT_MEDIA_FIXTURES с sound.wav и clip.mp4"]
    fn native_fixture_decode() {
        let root = std::path::PathBuf::from(
            std::env::var_os("XOPILOT_MEDIA_FIXTURES")
                .unwrap(),
        );
        for (name, video) in [
            ("sound.wav", false),
            ("clip.mp4", true),
            ("one.mp4", true),
            ("rotated.mp4", true),
            ("speech.mp3", false),
        ] {
            let path = root.join(name);
            let bytes = std::fs::read(&path).unwrap();
            let prepared = prepare(
                &path,
                &bytes,
                video,
                &CancellationToken::new(),
            )
            .unwrap_or_else(|error| {
                panic!("{name}: {error:#}")
            });
            println!(
                "{name}: frames={} audio={} duration={} warning={}",
                prepared.frames.len(),
                prepared.audio.is_some(),
                prepared.duration,
                prepared.warning
            );
            super::super::media::validate(&prepared)
                .unwrap();
            if name == "one.mp4" {
                assert_eq!(prepared.frames.len(), 1);
            }
            if name == "rotated.mp4" {
                let bytes = BASE64_STANDARD
                    .decode(&prepared.frames[0].data)
                    .unwrap();
                let picture =
                    image::load_from_memory(&bytes)
                        .unwrap();
                assert_eq!(
                    (picture.width(), picture.height()),
                    (240, 320)
                );
                let reference = image::open(
                    root.join("rotated-reference.png"),
                )
                .unwrap()
                .to_rgb8();
                let actual = picture.to_rgb8();
                let difference: f64 = actual
                    .as_raw()
                    .iter()
                    .zip(reference.as_raw())
                    .map(|(left, right)| {
                        f64::from(left.abs_diff(*right))
                    })
                    .sum::<f64>()
                    / actual.as_raw().len() as f64;
                assert!(
                    difference < 20.0,
                    "Неверное направление поворота, отличие {difference}"
                );
            }
        }
    }

    #[test]
    fn resampling_and_nal_validation_are_bounded() {
        let bytes = wav(&vec![0.5; 44100], 44100);
        super::super::media::validate_wav(&bytes).unwrap();
        assert_eq!(bytes.len(), 32044);
        assert!(annex_b(&[0, 0, 0, 5, 1], 4).is_err());
        assert_eq!(
            annex_b(&[0, 0, 0, 1, 42], 4).unwrap(),
            [0, 0, 0, 1, 42]
        );
    }
}
