"""
Phantom Scan Project — RF Validation Package
Brief: Test infrastructure for validating dual-target through-wall (NLOS)
       CSI sensing performance per VTP-PS-002 protocol.

Modules:
    phase_sanitizer:       SFO/PDD removal via cross-subcarrier regression
    nlos_capture:          120s UDP capture logger with full subcarrier data
    dual_target_analyzer:  Offline analysis: PSD, variance mapping, SNR, plotting
"""
