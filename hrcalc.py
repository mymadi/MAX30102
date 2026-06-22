# =========================================================================================
# 🫀 CLINICAL OPTICAL ALGORITHM (hrcalc.py)
# =========================================================================================
# Description:
#   This module processes raw Photoplethysmography (PPG) data from the MAX30102 
#   optical sensor. It uses the physical properties of light absorption in human 
#   blood to calculate real-time physiological metrics.
#
# 🩸 1. SpO2 (Blood Oxygen Saturation) Theory:
#   Oxygenated hemoglobin absorbs more Infrared (IR) light and lets Red light pass.
#   Deoxygenated hemoglobin absorbs more Red light and lets IR light pass.
#   This algorithm separates the signal into two parts:
#     - DC (Direct Current): The constant light blocked by solid tissue, bone, and skin.
#     - AC (Alternating Current): The pulsating light blocked by fresh blood pumping.
#   By calculating the ratio (R) of AC/DC for Red light vs. AC/DC for IR light, we 
#   use a standard clinical empirical polynomial formula to determine the oxygen %.
#
# 💓 2. Heart Rate (BPM) Peak Detection Theory:
#   The algorithm tracks the IR light wave. Every time the heart pumps (systole),
#   a surge of blood enters the capillary, causing a sudden spike in light absorption.
#   The script detects these "peaks", measures the average time interval between 
#   each spike, and multiplies by the hardware sample rate to get Beats Per Minute.
#
# =========================================================================================

def calc_hr_and_spo2(ir_data, red_data):
    """
    Calculates Heart Rate and SpO2 from raw Red and IR sensor data.
    Returns: (hr, hr_valid, spo2, spo2_valid)
    """
    # Ensure we have enough data (standard requirement is 100 samples)
    if len(ir_data) < 100 or len(red_data) < 100:
        return 0, False, 0, False

    # ---------------------------------------------------------
    # STEP 1: Calculate DC mean and AC variance for IR light
    # ---------------------------------------------------------
    ir_mean = sum(ir_data) / len(ir_data)
    ir_ac_sq_sum = sum((x - ir_mean) ** 2 for x in ir_data)
    ir_ac_rms = (ir_ac_sq_sum / len(ir_data)) ** 0.5

    # ---------------------------------------------------------
    # STEP 2: Calculate DC mean and AC variance for Red light
    # ---------------------------------------------------------
    red_mean = sum(red_data) / len(red_data)
    red_ac_sq_sum = sum((x - red_mean) ** 2 for x in red_data)
    red_ac_rms = (red_ac_sq_sum / len(red_data)) ** 0.5

    # ---------------------------------------------------------
    # STEP 3: Calculate SpO2 using empirical ratio formula
    # Formula: R = (AC_Red / DC_Red) / (AC_IR / DC_IR)
    # ---------------------------------------------------------
    try:
        r_num = (red_ac_rms / red_mean)
        r_den = (ir_ac_rms / ir_mean)
        r = r_num / r_den
        
        # Standard clinical SpO2 empirical polynomial formula
        spo2 = -45.060 * (r ** 2) + 30.354 * r + 94.845
        spo2 = int(spo2)
        
        # Validate that the SpO2 is within humanly possible boundaries
        spo2_valid = True if 70 <= spo2 <= 100 else False
        if spo2 > 100: 
            spo2 = 99
            
    except ZeroDivisionError:
        spo2 = 0
        spo2_valid = False

    # ---------------------------------------------------------
    # STEP 4: Calculate Heart Rate (Peak Detection)
    # ---------------------------------------------------------
    peaks = []
    
    # Scan through the IR wave looking for local maximums (peaks)
    for i in range(1, len(ir_data) - 1):
        # A peak is defined as a point higher than the point before and after it
        if ir_data[i] > ir_data[i-1] and ir_data[i] > ir_data[i+1]:
            # Filter out minor noise ripples by ensuring it's above the overall average
            if ir_data[i] > ir_mean:
                peaks.append(i)

    hr = 0
    hr_valid = False
    
    # If we found at least 2 heartbeats, calculate the time between them
    if len(peaks) >= 2:
        # Calculate average distance (in samples) between peaks
        intervals = [peaks[i] - peaks[i-1] for i in range(1, len(peaks))]
        avg_interval = sum(intervals) / len(intervals)
        
        # Assume a standard polling sample rate of ~25Hz from the I2C bus
        sample_rate = 25 
        
        # Convert the sample interval into Beats Per Minute (60 seconds)
        hr = int((60 * sample_rate) / avg_interval)
        
        # Validate that the HR is within humanly possible boundaries
        if 40 <= hr <= 220:
            hr_valid = True
        else:
            hr_valid = False

    # Return the final calculated physiological values back to the main script
    return hr, hr_valid, spo2, spo2_valid
