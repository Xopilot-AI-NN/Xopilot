Source: https://github.com/SUC-DriverOld/rvc.onnx

Revision: 4de2fd8f895321c506db14df0c102a2f74820005

MIT licensed (Copyright 2026 Sucial). Full RVC v2 architecture is retained. Imports use this local package; SineGen receives caller-owned Gaussian excitation noise for deterministic ONNX parity and cancellation-safe runtime execution. Attention helpers use embedded TorchScript CompilationUnit source so export also works from Flet's bytecode-only packages. No inference weights are discarded or approximated. The upstream RVC-Project MIT notice is preserved in LICENSE.rvc.
