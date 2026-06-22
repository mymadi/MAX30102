# IoT Bio-Telemetry Sensor Engine

This repository contains a standalone, bare-metal CircuitPython firmware designed to interface directly with a MAX30102 Pulse Oximeter and Heart Rate sensor. It utilizes a Raspberry Pi Pico W to capture raw optical data, process it locally through digital signal filtering, and output real-time physiological metrics and algorithmic estimations directly to the serial console.

---

## 🔌 Hardware Wiring Map

This firmware requires a **Raspberry Pi Pico W** (or standard RP2040) and a **MAX30102** sensor. 

| Sensor Pin | Raspberry Pi Pico W Pin |
| :--- | :--- |
| **VCC** | 3.3V OUT (Physical Pin 36) |
| **GND** | GND (Physical Pin 38 or any Ground) |
| **SDA** | GP2 (Physical Pin 4) - I2C Bus 1 |
| **SCL** | GP3 (Physical Pin 5) - I2C Bus 1 |

---

## ⚙️ Software Architecture

The codebase is split into two modular files to separate heavy mathematical processing from the main hardware execution loop.

### 1. `code.py` (The Execution Engine)
This is the main loop running on the microcontroller. 
* It establishes the I2C bus and manages the sensor's power states (waking it up and shutting it down to save power).
* It acts as a "Gatekeeper," rapidly polling the sensor's infrared values to detect when a finger is placed on the sensor.
* Once a finger is detected, it collects a rolling block of 100 raw red and infrared light samples at ~25Hz.
* It passes this raw data to the math library, retrieves the true physical metrics, and runs them through clinical estimation formulas before printing the final diagnostic summary to the serial console.

### 2. `hrcalc.py` (The Mathematical Filter)
This library isolates the complex signal processing logic. It filters the Direct Current (DC) and Alternating Current (AC) from the raw light arrays, executes peak-detection to find the pulse, and applies the standard empirical polynomial formula to calculate blood oxygen saturation.

---

## 🧮 Clinical Algorithms & Formulas

The vital sign outputs are divided into two categories: **True Optical Calculations** (derived physically from light absorption) and **Algorithmic Estimations** (derived mathematically using correlation models).

### True Optical Calculations (`hrcalc.py`)

These metrics rely on the physical properties of human hemoglobin. Oxygenated blood absorbs more Infrared (IR) light, while deoxygenated blood absorbs more Red light. 

* **Heart Rate (Peak Detection):** The algorithm tracks the IR light wave, filtering out noise. It detects local maximums (peaks) representing the systolic pump of the heart. The time interval between peaks is averaged to find the Beats Per Minute (BPM):
  $$HR = \frac{60 \times SampleRate}{AverageInterval}$$

* **Blood Oxygen Saturation (SpO2):**
  The script isolates the constant light absorption (DC) from the pulsating blood volume (AC) to find the Ratio ($R$):
  $$R = \frac{AC_{red} / DC_{red}}{AC_{ir} / DC_{ir}}$$
  The final SpO2 percentage is calculated using a standard empirical clinical polynomial:
  $$SpO2 = -45.060 \times R^2 + 30.354 \times R + 94.845$$

* **Perfusion Index (PI):**
  This measures the ratio of pulsating blood flow to static non-pulsating blood in the peripheral tissue.
  $$PI = \left( \frac{IR_{max} - IR_{min}}{IR_{mean}} \right) \times 100$$

### Algorithmic Estimations (`code.py`)

Because a non-invasive optical finger sensor cannot physically extract blood or physically compress an artery, the following metrics use mathematical correlation models. They calculate deviations from a theoretical healthy baseline using the verified Heart Rate, SpO2, and the physical amplitude of the pulse wave to simulate secondary vitals.

* **Blood Pressure (Estimated):**
  Correlates the strength of the physical pulse wave amplitude ($\Delta Amp$) and heart rate elevation ($\Delta HR$) to simulate systolic and diastolic pressure.
  $$Sys = 120 + (\Delta HR \times 0.4) + (\Delta Amp \times 0.005)$$
  $$Dia = 80 + (\Delta HR \times 0.2) + (\Delta Amp \times 0.002)$$

* **Blood Glucose (Estimated):**
  A simulated correlation model. Elevated resting heart rates combined with slightly lowered blood oxygen levels in non-active states can correlate with metabolic stress and elevated glucose.
  $$Glucose = 5.5 + (\Delta HR \times 0.03) + ((98 - SpO2) \times 0.15)$$

* **Cholesterol (Estimated):**
  Simulates cardiovascular strain based on resting pulse rate and oxygen efficiency.
  $$Cholesterol = 4.8 + (\Delta HR \times 0.02) + ((98 - SpO2) \times 0.08)$$

---

## ⚠️ Disclaimer
*This repository contains an open-source engineering prototype and algorithmic proof-of-concept. It is not FDA-approved and should not be used as a substitute for professional, medical-grade diagnostic equipment.*
