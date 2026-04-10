# Context
You are an expert robotics software engineer specializing in autonomous agricultural machinery. Your task is to implement a deterministic, edge-computed navigation and avoidance system. The target hardware is an NVIDIA Jetson AGX Orin. The software stack should be based on ROS2 (Humble/Iron) and Python/C++, utilizing TensorRT for neural network inference and NumPy/Eigen for deterministic control math.

# System Architecture
The system consists of a Perception Stack and a Control Engine operating in a strict, high-frequency closed loop (>30 FPS). It completely excludes heavy Vision-Language Models from the control loop to ensure zero-latency deterministic response.

## 1. Perception Stack Interfaces
You will build the control logic assuming the following inputs are provided by upstream ROS2 topics from the perception layer:
* **Kinematics Array:** `[id, class, x, y, v_x, v_y]` for all detected dynamic entities (provided by YOLOv10 + ByteTrack).
* **Semantic Graph Array:** `[id, certainty (c_i), danger_quality (q_i)]` for all entities (provided by a TensorRT-optimized SGG).
* **Crop Occupancy Grid:** A 2D array $P_{crop}(x, y)$ representing the semantic probability of unharvested crop/working zones.

## 2. Control Engine: Dual-System Vector APF
Implement the Artificial Potential Field (APF) mathematically decoupled into Lateral (Steering) and Longitudinal (Velocity) controllers.

### A. Lateral Control (Steering)
Implement a Proportional-Derivative (PD) contour tracker competing with predictive repulsive vectors.

**1. Crop Contour Tracking:**
Calculate the spatial gradient $\nabla P_{crop}$ to find the field edge. Define an ideal lateral offset $D_{target}$.
Generate an attractive steering vector $A_{edge}$ using a PD controller minimizing the cross-track error to $D_{target}$.

**2. Predictive Avoidance:**
Project hazard positions forward by lookahead time $t$:
$$P_{predicted} = (x_i + v_{x,i} \cdot t, y_i + v_{y,i} \cdot t)$$

Generate repulsive steering vectors $S_i$:
$$S_i = - \text{sgn}(x_{pred,i}) \cdot \left( \frac{c_i \cdot q_i}{\sqrt{x_{pred,i}^2 + y_{pred,i}^2} + \epsilon} \right) \cdot f(y_{pred,i})$$
*(Where $\epsilon$ is a small constant to prevent division by zero, and $f(y)$ is a distance decay function).*

**3. Vector Resolution:**
Sum and clamp the vectors to the machine's physical steering limits $\theta_{max}$:
$$\Delta \theta = \max \left(-\theta_{max}, \min \left(\theta_{max}, A_{edge} + W_{rep} \sum S_i(P_{predicted}) \right) \right)$$
*(Where $W_{rep}$ is a tunable global repulsion weight).*

### B. Longitudinal Control (Velocity)
Implement a safety-corridor protocol that overrides all lateral logic.

**1. Safety Corridor Check:**
Define a forward geometric polygon based on current $V_{base}$, $\theta_{max}$, and the machine's width. Define a boolean function `InCorridor(x, y)` that returns 1 if a point is within this polygon, and 0 otherwise.

**2. Vehicle Braking Protocol:**
Calculate the target velocity based on the most critical hazard in the corridor:
$$V_{target} = V_{base} \cdot \left( 1 - \max_{i} \left( \frac{c_i \cdot q_i}{y_{pred,i}} \cdot \text{InCorridor}(x_{pred,i}) \right) \right)$$
Clamp the final command: $0 \le V_{target} \le V_{max}$. If a high-quality danger (e.g., human) intersects the corridor with high certainty, this must instantly evaluate to 0 (hard brake).
