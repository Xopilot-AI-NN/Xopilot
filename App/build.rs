// Описание: Встраиваем библиотеку целевой платформы в приложение, без Python/JNI-пакетов.
use std::{env, fs, path::PathBuf};
fn main() {
    let target = env::var("TARGET").unwrap();
    let platform = match target.as_str() {
        "x86_64-unknown-linux-gnu" => "linux_x86_64",
        "aarch64-unknown-linux-gnu" => "linux_arm64",
        "aarch64-linux-android" => "android_arm64",
        "x86_64-linux-android" => "android_x86_64",
        _ => "unsupported",
    };
    let source = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap())
        .join("native")
        .join(platform)
        .join("liblitert-lm.so");
    println!("cargo:rerun-if-changed={}", source.display());
    println!(
        "cargo:rustc-env=XOPILOT_LITERT_BUNDLED={}",
        if source.is_file() { "1" } else { "0" }
    );
    let destination = PathBuf::from(env::var("OUT_DIR").unwrap()).join("liblitert-lm.so");
    // SDK поставляет .so с правами 0555; удаляем прежнюю копию перед пересборкой.
    if destination.exists() {
        fs::remove_file(&destination).unwrap();
    }
    if source.is_file() && target.contains("android") {
        // DX копирует абсолютные .so из link args в jniLibs нужного ABI.
        // Android загружает библиотеку из APK, а не исполняет код из каталога данных.
        println!("cargo:rustc-link-arg={}", source.display());
        fs::write(&destination, []).unwrap();
    } else if source.is_file() {
        fs::copy(source, &destination).unwrap();
    } else {
        fs::write(&destination, []).unwrap();
    }
    let notices =
        PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap()).join("native/runtime-licenses.zip");
    println!("cargo:rerun-if-changed={}", notices.display());
    let output = PathBuf::from(env::var("OUT_DIR").unwrap()).join("runtime-licenses.zip");
    if notices.is_file() {
        fs::copy(notices, output).unwrap();
    } else {
        fs::write(output, []).unwrap();
    }
}
