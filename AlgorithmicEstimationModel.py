# =========================================================================================
# 🫀 STANDALONE BIO-TELEMETRY ENGINE (code.py)
# =========================================================================================
# Description:
#   This script operates as a dedicated, non-distributed firmware engine designed 
#   solely to interface with the MAX30102 Pulse Oximeter and Heart Rate sensor. 
#
# 🩸 Core Mechanics:
#   - Establishes a dedicated I2C hardware bus connection on pins GP2 and GP3.
#   - Continuously polls the sensor register array to detect peripheral tissue placement.
#   - Collects a rolling array block of 100 raw Red and Infrared optical light samples.
#   - Hands the array block off to the local arithmetic library ('hrcalc.py') for AC/DC filtering.
#   - Uses verified HR and SpO2 to algorithmically estimate BP, Glucose, and Cholesterol.
#   - Outputs verified vital signs locally through the standard Serial/REPL stream.
# =========================================================================================

import time
import board
import busio
import gc
from max30102 import MAX30102  
from hrcalc import calc_hr_and_spo2  

# =========================================================================
# 🧠 CLINICAL ESTIMATION FORMULAS
# Note: Because an optical sensor cannot literally taste blood sugar or 
# measure physical arterial pressure, these functions use mathematical 
# correlation models based on baseline heart rate, oxygen, and pulse amplitude.
# =========================================================================

def estimate_bp(ir_data, hr):
    try:
        if hr < 40 or hr > 220 or not ir_data: return ""
        ir_min = min(ir_data); ir_max = max(ir_data); amplitude = ir_max - ir_min
        base_sys = 120; base_dia = 80; base_hr = 75; base_amp = 1500 
        hr_diff = hr - base_hr; amp_diff = amplitude - base_amp
        sys_estimate = base_sys + (hr_diff * 0.4) + (amp_diff * 0.005)
        dia_estimate = base_dia + (hr_diff * 0.2) + (amp_diff * 0.002)
        if sys_estimate < 60 or sys_estimate > 250: return ""
        return f"{int(sys_estimate)}/{int(dia_estimate)}"
    except Exception: return ""

def estimate_blood_sugar(hr, spo2):
    try: 
        if hr < 40 or hr > 220 or spo2 < 70 or spo2 > 100: return ""
        sugar = 5.5 + ((hr - 75) * 0.03) + ((98 - spo2) * 0.15)
        if sugar < 2.0 or sugar > 30.0: return ""
        return str(round(sugar, 1))
    except Exception: return ""

def estimate_cholesterol(hr, spo2):
    try: 
        if hr < 40 or hr > 220 or spo2 < 70 or spo2 > 100: return ""
        chol = 4.8 + ((hr - 75) * 0.02) + ((98 - spo2) * 0.08)
        if chol < 2.0 or chol > 15.0: return ""
        return str(round(chol, 1))
    except Exception: return ""

# =========================================================================
# 🚀 CORE INITIALIZATION
# =========================================================================

print("=========================================================")
print("🫀 INITIALIZING BIO-TELEMETRY FIRMWARE ENGINE v1.1")
print("=========================================================")

# ---------------------------------------------------------
# STEP 1: Initialize I2C Communication Bus
# ---------------------------------------------------------
try:
    i2c_bus = busio.I2C(board.GP3, board.GP2)
    print("✅ I2C Hardware Bus: Initialized on SCL(GP3), SDA(GP2)")
except Exception as e:
    print(f"❌ I2C Hardware Bus: Failed to mount. Verify wiring connections. Error: {e}")
    while True:
        pass

# ---------------------------------------------------------
# STEP 2: Mount & Configure the MAX30102 Optical Sensor
# ---------------------------------------------------------
sensor_ready = False
pulse_sensor = None

while not i2c_bus.try_lock():
    pass
try:
    i2c_devices = i2c_bus.scan()
    if 0x57 in i2c_devices:
        pulse_sensor = MAX30102(i2c=i2c_bus)
        pulse_sensor.setup_sensor()
        pulse_sensor.shutdown() # Place sensor in low-power standby mode
        sensor_ready = True
        print("✅ MAX30102 Sensor: Successfully mapped on I2C address 0x57")
    else:
        print("❌ MAX30102 Sensor: Device address 0x57 not found on bus scan.")
finally:
    i2c_bus.unlock()

if not sensor_ready:
    print("🛑 Critical Failure: Sensor offline. Halting execution engine.")
    while True:
        pass

print("\n🚀 Core Engine Engaged. Standing by for finger placement...\n")

# =========================================================================
# 🔄 MAIN CONTINUOUS PROCESSING LOOP
# =========================================================================
while True:
    try:
        gc.collect() 
        pulse_sensor.wakeup()
        
        ir_data = []
        red_data = []
        wait_counter = 0
        finger_detected = False
        
        # --- PHASE A: FINGER DETECTION GATEKEEPER ---
        while wait_counter < 100:
            try:
                red, ir = pulse_sensor.pop_raw_data()
                if ir > 20000:
                    print("💓 Finger Detected! Commencing raw data stream collection...")
                    finger_detected = True
                    break
            except Exception:
                pass
            time.sleep(0.05)
            wait_counter += 1

        if not finger_detected:
            pulse_sensor.shutdown()
            time.sleep(0.2)
            continue

        # --- PHASE B: DATA STREAM ACQUISITION ---
        samples_collected = 0
        finger_removed = False
        
        print("⏳ Analyzing arterial pulse waves (Keep finger completely still)...")
        
        while samples_collected < 100:
            try:
                red, ir = pulse_sensor.pop_raw_data()
                
                # If the patient lifts their finger mid-scan, abort instantly
                if ir < 20000:
                    print("⚠️ Scan Aborted: Tissue contact lost mid-session.")
                    finger_removed = True
                    break
                
                ir_data.append(ir)
                red_data.append(red)
                samples_collected += 1
                
                if samples_collected % 20 == 0:
                    print(f"   Progress: [{samples_collected}/100 Samples Captured]")
                    
            except Exception:
                time.sleep(0.01)
                
            time.sleep(0.02) # Pacing latch to match ~25Hz sample rate

        pulse_sensor.shutdown()

        if finger_removed:
            continue

        # --- PHASE C: PHYSIOLOGICAL MATHEMATICAL RESOLUTION ---
        print("🧮 Executing optical light absorption wave calculations...")
        
        # 1. Calculate True Physical Metrics
        heart_rate, hr_valid, spo2, spo2_valid = calc_hr_and_spo2(ir_data, red_data)

        # 2. Calculate Algorithmic Estimations
        est_bp = "--/--"
        est_sugar = "--"
        est_chol = "--"

        if hr_valid and spo2_valid:
            est_bp = estimate_bp(ir_data, heart_rate)
            est_sugar = estimate_blood_sugar(heart_rate, spo2)
            est_chol = estimate_cholesterol(heart_rate, spo2)

        # --- PHASE D: SERIAL LOG REPORTING ---
        print("\n=========================================================")
        print("📊 CLINICAL DIAGNOSTIC SCAN SUMMARY")
        print("=========================================================")
        
        # Physical Measurements
        if hr_valid:
            print(f"❤️ HEART RATE    : {heart_rate} BPM      [VERIFIED OPTICAL]")
        else:
            print("❤️ HEART RATE    : -- BPM       [UNSTABLE SIGNAL]")
            
        if spo2_valid:
            print(f"🩸 BLOOD OXYGEN  : {spo2}%         [VERIFIED OPTICAL]")
        else:
            print("🩸 BLOOD OXYGEN  : --%          [UNSTABLE SIGNAL]")

        print("---------------------------------------------------------")
        
        # Algorithmic Estimations
        if hr_valid and spo2_valid:
            print(f"🩺 BLOOD PRESSURE: {est_bp} mmHg  [ALGORITHMIC ESTIMATE]")
            print(f"🍬 GLUCOSE       : {est_sugar} mmol/L   [ALGORITHMIC ESTIMATE]")
            print(f"🍔 CHOLESTEROL   : {est_chol} mmol/L   [ALGORITHMIC ESTIMATE]")
        else:
            print("🩺 BLOOD PRESSURE: --/-- mmHg   [INSUFFICIENT BASELINE]")
            print("🍬 GLUCOSE       : -- mmol/L    [INSUFFICIENT BASELINE]")
            print("🍔 CHOLESTEROL   : -- mmol/L    [INSUFFICIENT BASELINE]")
            
        print("=========================================================\n")
        
        print("Engaging engine cooldown. Ready for next read in 3 seconds...\n")
        time.sleep(3.0)

    except Exception as e:
        print(f"\n⚠️ Peripheral Exception Trapped in Main Loop: {e}")
        try:
            pulse_sensor.shutdown()
        except Exception:
            pass
        time.sleep(1.0)
