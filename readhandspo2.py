# =========================================================================================
# 🫀 STANDALONE BIO-TELEMETRYCommand ENGINE (code.py)
# =========================================================================================
# Description:
#   This script operates as a dedicated, non-distributed firmware engine designed 
#   solely to interface with the MAX30102 Pulse Oximeter and Heart Rate sensor. 
#   It completely bypasses all external cloud communication protocols to minimize 
#   processing latency on the RP2040 microcontroller chip.
#
# 🩸 Core Mechanics:
#   - Establishes a dedicated I2C hardware bus connection on pins GP2 and GP3.
#   - Continuously polls the sensor register array to detect peripheral tissue placement (finger tap).
#   - Collects a rolling array block of 100 raw Red and Infrared optical light samples.
#   - Hands the array block off to the local arithmetic library ('hrcalc.py') for AC/DC filtering.
#   - Outputs verified vital signs locally through the standard Serial/REPL stream.
# =========================================================================================

import time
import board
import busio
import gc
from max30102 import MAX30102  
from hrcalc import calc_hr_and_spo2  

print("=========================================================")
print("🫀 INITIALIZING BIO-TELEMETRY FIRMWARE ENGINE v1.0")
print("=========================================================")

# ---------------------------------------------------------
# STEP 1: Initialize I2C Communication Bus
# ---------------------------------------------------------
# Creates a hardware I2C instance. Adjust the pins below if your 
# physical sensor wiring utilizes a different GP register layout.
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

# Scan the I2C bus looking for the standard MAX30102 target address (0x57)
while not i2c_bus.try_lock():
    pass
try:
    i2c_devices = i2c_bus.scan()
    if 0x57 in i2c_devices:
        pulse_sensor = MAX30102(i2c=i2c_bus)
        pulse_sensor.setup_sensor()
        pulse_sensor.shutdown() # Place sensor in low-power standby mode until active request
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

# ---------------------------------------------------------
# STEP 3: Main Continuous Processing Loop
# ---------------------------------------------------------
while True:
    try:
        # Force garbage collection at the start of each check to clear RAM heaps
        gc.collect() 
        
        # Wake up the photodiode LEDs on the optical sensor array
        pulse_sensor.wakeup()
        
        ir_data = []
        red_data = []
        wait_counter = 0
        finger_detected = False
        
        # --- PHASE A: FINGER DETECTION GATEKEEPER ---
        # Poll the sensor rapidly. If the Infrared reflection reading spikes over 20,000, 
        # it mathematically indicates a dense organic mass is directly covering the LED array.
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

        # If no finger was placed over the sensor during the polling block, loop back to standby
        if not finger_detected:
            pulse_sensor.shutdown()
            time.sleep(0.2)
            continue

        # --- PHASE B: DATA STREAM ACQUISITION ---
        # The clinical math library requires a rolling window block of 100 stable 
        # sequential samples to accurately separate the pulsing blood flow from background static tissue noise.
        samples_collected = 0
        finger_removed = False
        
        print("⏳ Analyzing arterial pulse waves (Keep finger completely still)...")
        
        while samples_collected < 100:
            try:
                red, ir = pulse_sensor.pop_raw_data()
                
                # If the patient lifts their finger mid-scan, abort instantly to prevent corrupted logs
                if ir < 20000:
                    print("⚠️ Scan Aborted: Tissue contact lost mid-session.")
                    finger_removed = True
                    break
                
                ir_data.append(ir)
                red_data.append(red)
                samples_collected += 1
                
                # Visual ticking feedback via text stream
                if samples_collected % 20 == 0:
                    print(f"   Progress: [{samples_collected}/100 Samples Captured]")
                    
            except Exception:
                time.sleep(0.01)
                
            time.sleep(0.02) # Standard pacing latch to match the 25Hz sample matrix rate

        # Put the sensor photodiodes back to sleep immediately to extend hardware lifespan
        pulse_sensor.shutdown()

        if finger_removed:
            continue

        # --- PHASE C: PHYSIOLOGICAL MATHEMATICAL RESOLUTION ---
        print("🧮 Executing optical light absorption wave calculations...")
        
        # Send the raw array data blocks directly to your 'hrcalc.py' library file
        heart_rate, hr_valid, spo2, spo2_valid = calc_hr_and_spo2(ir_data, red_data)

        # --- PHASE D: SERIAL LOG REPORTING ---
        print("\n=========================================================")
        print("📊 CLINICAL DIAGNOSTIC SCAN SUMMARY")
        print("=========================================================")
        
        if hr_valid:
            print(f"❤️ HEART RATE : {heart_rate} BPM  [VERIFIED]")
        else:
            print("❤️ HEART RATE : -- BPM  [UNSTABLE SIGNAL / ARTIFACT ERR]")
            
        if spo2_valid:
            print(f"🩸 BLOOD OXYGEN: {spo2}%     [VERIFIED]")
        else:
            print("🩸 BLOOD OXYGEN: --%      [UNSTABLE SIGNAL / ARTIFACT ERR]")
            
        print("=========================================================\n")
        
        # Enforce a short physical breathing delay before allowing another sequential vital scan
        print("Engaging engine cooldown. Ready for next read in 3 seconds...\n")
        time.sleep(3.0)

    except Exception as e:
        print(f"\n⚠️ Peripheral Exception Trapped in Main Loop: {e}")
        try:
            pulse_sensor.shutdown()
        except Exception:
            pass
        time.sleep(1.0)
