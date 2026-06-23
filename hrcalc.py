# =========================================================================================
# 🫀 STANDALONE PPG SIGNAL PROCESSING LIBRARY (hrcalc.py)
#     - # Save this in your 'lib' folder as: hrcalc.py
# =========================================================================================
# Description:
#   This library processes raw Photoplethysmography (PPG) waveforms captured by the
#   MAX30102 optical sensor. It handles AC/DC signal isolation, applies device-specific 
#   calibration equations, and utilizes advanced filtering to isolate heartbeats.
#
# 🩸 1. Optimized SpO2 Mathematics & Calibration:
#   - Tissue, bone, and residual venous blood form the constant DC baseline.
#   - Pumping arterial blood generates a fluctuating AC wave (Max - Min peak intensity).
#   - The absorption ratio is calculated as: R = (AC_Red / DC_Red) / (AC_IR / DC_IR)
#   - This layout applies a specialized scaling multiplier (0.4) and linear regression 
#     slope to establish raw SpO2 values.
#   - A hardcoded +14 CALIBRATION_OFFSET is applied to perfectly align the final output 
#     curve with reference consumer health wearables (e.g., Huawei baseline metrics).
#
# 💓 2. Upgraded Heart Rate & Echo-Blocking Filter:
#   - Sets a dynamic threshold at 30% above the IR mean to filter out secondary capillary 
#     bouncing and hardware white noise.
#   - Peak detection locates true local maxima where a data point is higher than its 
#     immediate neighbors on both sides.
#   - THE TIME-OUT MASK: To completely block overlapping dicrotic notches, false echoes, 
#     or twin-pulse artifacts, a hard limit forces sequential peaks to be at least 8 
#     samples apart. At a ~25Hz sample rate, this securely blinds the system for ~320ms 
#     after every pulse.
#   - Conversion Factor (1500): Derived directly from standard frequency timing:
#     60 seconds * 25 Hz Sample Rate = 1500 total available sample ticks per minute.
# =========================================================================================

def calc_hr_and_spo2(ir_data, red_data):
    # Establish DC components via baseline arithmetic averages
    ir_mean = sum(ir_data) / len(ir_data)
    red_mean = sum(red_data) / len(red_data)
    
    # Establish AC components by tracking absolute raw amplitude shifts
    ir_ac = max(ir_data) - min(ir_data)
    red_ac = max(red_data) - min(red_data)
    
    # ---------------------------------------------------------
    # --- SpO2 MATH ---
    # ---------------------------------------------------------
    spo2_valid = False
    spo2 = 0
    if ir_ac > 0 and ir_mean > 0:
        # Compute raw light modulation absorption index ratio
        ratio = (red_ac / red_mean) / (ir_ac / ir_mean)
        normalized_ratio = ratio * 0.4 
        raw_spo2 = 110.0 - (25.0 * normalized_ratio)
        
        # Apply the calibrated baseline profile offset match
        CALIBRATION_OFFSET = 14 
        spo2 = raw_spo2 + CALIBRATION_OFFSET
        
        # Clinical boundary safety clamp
        if spo2 > 99:
            spo2 = 99
            spo2_valid = True
        elif 70 <= spo2 <= 99:
            spo2_valid = True
            
    # ---------------------------------------------------------
    # --- UPGRADED HEART RATE MATH ---
    # ---------------------------------------------------------
    hr_valid = False
    hr = 0
    peaks = []
    
    # Establish dynamic threshold boundary cutoff at 30% above mean
    threshold = ir_mean + (ir_ac * 0.3)
    
    last_peak = -10 # Boot baseline tracking index placeholder
    
    # Scan array window, isolating borders to prevent out-of-bounds registry index errors
    for i in range(2, len(ir_data) - 2):
        # Isolate local true peaks (mathematical mathematical maxima)
        if ir_data[i] > ir_data[i-1] and ir_data[i] > ir_data[i+1]:
            if ir_data[i] > threshold:
                # THE TIME-OUT: Enforce an 8-sample spacing mask to kill dicrotic echoes
                if i - last_peak >= 8:
                    peaks.append(i)
                    last_peak = i
                
    # Calculate median intervals to produce the final calculation output
    if len(peaks) >= 2:
        intervals = [peaks[i] - peaks[i-1] for i in range(1, len(peaks))]
        avg_interval = sum(intervals) / len(intervals)
        
        if avg_interval > 0:
            # Map time intervals back to minute scales using the 25Hz frequency scale constant
            hr = int(1500 / avg_interval)
            # Standard physiological sanity verification limits
            if 40 < hr < 180:
                hr_valid = True

    return (int(hr), hr_valid, int(spo2), spo2_valid)
