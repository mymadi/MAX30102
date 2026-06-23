# =========================================================================================
# 🫀 STANDALONE BIO-TELEMETRY FIRMWARE CORE (code.py)
# =========================================================================================
# Description:
#   Main execution firmware for an isolated RP2040 bio-telemetry application. 
#   Interfaces directly with the MAX30102 optical array over a stabilized I2C bus.
#   Streamlined strictly for raw physical heart rate and SpO2 calculation blocks.
#
# 📋 Micro-Execution Pipeline:
#   1. BUS STABILIZATION : Injects a 1000ms delay allowing the sensor chip to stable-boot 
#                          before the microcontroller polls register identities.
#   2. SIGNAL ACQUISITION: Rapidly checks IR intensity to verify physical tissue contact 
#                          (finger placement gatekeeper).
#   3. BUFFER WINDOWING  : Fills a 100-sample raw data array block at ~25Hz. Once full, 
#                          it offloads calculation tasks to the local library.
#   4. MATRIX SHIFTING   : Drops the oldest 25 samples via array slicing ([25:]) to maintain 
#                          a running memory footprint and prevent RAM heap corruption.
#   5. MEDIAN RECOVERY   : Sorts confirmed vital logs to extract median values, completely 
#                          filtering out motion artifacts or accidental finger wiggles.
#   6. SOLID SHUTDOWN    : Forces hardware registers to explicitly turn off the red and IR 
#                          lasers when processing completes to maximize sensor lifetime.
# =========================================================================================

import time
import board
import busio
from max30102 import MAX30102
from hrcalc import calc_hr_and_spo2

# =========================================================================================
# 🔌 HARDWARE INITIALIZATION SEQUENCE
# =========================================================================================

print("=========================================================")
print("🫀 INITIALIZING OPTICAL TELEMETRY FIRMWARE ENGINE")
print("=========================================================")

# Bind physical I2C pins: SCL to GP3 (Pin 5) and SDA to GP2 (Pin 4)
i2c = busio.I2C(board.GP3, board.GP2)

# ⚡ THE HARDWARE CRASH FIX: Force a 1.0 second pause to let the sensor's internal
# power-on-reset hardware cycle complete safely before the Pico queries the bus lines.
print("Letting the sensor power up...")
time.sleep(1) 

# Secure the I2C bus lock configuration
while not i2c.try_lock():
    pass
try:
    devices = i2c.scan()
finally:
    i2c.unlock()

# Mount driver configuration map onto the active sensor target address
sensor = MAX30102(i2c=i2c)

if sensor.address not in devices:
    print("❌ CRITICAL: The sensor vanished! Verify hardware connections and bus layout.")
else:
    print("Booting MAX30102...")
    sensor.setup_sensor()
    print("✅ Sensor Ready. Place your finger gently on the glass!")

    # Local buffer structures to capture incoming optical telemetry streams
    ir_data = []
    red_data = []
    
    # Storage arrays to collect valid metrics before median sorting
    locked_hr = []
    locked_spo2 = []
    
    REQUIRED_SAMPLES = 10 

    # =====================================================================================
    # 🔄 DATA ACQUISITION & BUFFER WINDOWING LOOP
    # =====================================================================================
    while len(locked_hr) < REQUIRED_SAMPLES:
        try:
            # Extract raw 18-bit integer channel outputs from the hardware FIFO register
            red, ir = sensor.pop_raw_data()
            
            # CONTACT VERIFICATION FILTER: Readings below 30,000 signify open air noise.
            # If tissue contact is dropped, instantly reset memory data windows.
            if ir < 30000:
                if len(ir_data) > 0:
                    print("Finger removed. Resetting scanner matrix...")
                ir_data.clear()
                red_data.clear()
                locked_hr.clear() 
                locked_spo2.clear()
                time.sleep(0.05) 
                continue

            # Append clean optical raw data to running streaming lists
            ir_data.append(ir)
            red_data.append(red)

            # Execution block triggers when the window reaches the mandatory 100-sample limit
            if len(ir_data) >= 100:
                # Offload raw array blocks to the local signal processing library
                hr, hr_valid, spo2, spo2_valid = calc_hr_and_spo2(ir_data, red_data)

                if hr_valid and spo2_valid:
                    # Append stable values to the final sorting arrays
                    locked_hr.append(hr)
                    locked_spo2.append(spo2)
                    
                    current = len(locked_hr)
                    print(f"Locking in pulse profiles... {current}/{REQUIRED_SAMPLES} ⏳")
                else:
                    # Diagnostic status outputs for raw waveform tracking
                    print(f"Adjusting... (Math rejected anomalies -> HR: {hr} | SpO2: {spo2})")
                
                # MEMORY MANAGEMENT: Slide the array frame forward by slicing away the oldest 
                # 25 values. This retains 75 samples for the next rolling check and frees RAM heaps.
                ir_data = ir_data[25:]
                red_data = red_data[25:]
                
            time.sleep(0.04) # Enforces ~25Hz polling sync lock speed

        except Exception as e:
            print("Error reading sensor array registers:", e)
            time.sleep(1)

    # =====================================================================================
    # 📊 FINAL REPL REPORTING & RESOLUTIONS
    # =====================================================================================
    print("\n" + "=" * 50)
    print("🎉 SCAN COMPLETE! PROCESSING OPTICAL DATA SUMMARY")
    print("=" * 50)
    
    # ARTIFACT ELIMINATION: Sort confirmed readings sequentially and grab the central index (median).
    # This guarantees accidental movements or coughs do not warp final clinical output values.
    final_hr = sorted(locked_hr)[len(locked_hr) // 2]
    final_spo2 = sorted(locked_spo2)[len(locked_spo2) // 2]
    
    # Output pristine localized serial summaries
    print(f"👉 HEART RATE        : {final_hr} BPM      [OPTICAL VERIFIED]")
    print(f"👉 BLOOD OXYGEN      : {final_spo2} %       [OPTICAL VERIFIED]")
    print("=" * 50 + "\n")
    
    # =====================================================================================
    # 🛑 SAFE DEEP SHUTDOWN PROTOCOL
    # =====================================================================================
    print("Powering down sensor lasers safely...")
    while not i2c.try_lock(): 
        pass
    try: 
        # Overwrite mode configuration lines to force hardware LED drivers to 0.0mA current.
        # This completely shuts off the physical red light when scanning completes.
        i2c.writeto(0x57, bytes([0x0C, 0x00])) # Shut down physical Red LED channel
        i2c.writeto(0x57, bytes([0x0D, 0x00])) # Shut down physical IR LED channel
    finally: 
        i2c.unlock()
    
    print("Execution finalized cleanly. System on standby.")
