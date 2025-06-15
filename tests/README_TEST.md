## Running the Test Scripts

You have two primary options for executing the project's test scripts:

### Option 1: Running Each Phase Individually

This option allows you to test each phase by checking out its respective branch.

#### **Phase 1 & Phase 2 Tests:**

1.  **Switch to the Phase 2 branch:**
    ```bash
    git checkout tpphase2-covert-channel-ip-field-manipulation
    ```
    *(Note: Phase 1's code was merged into the main branch, and its foundational aspects are implicitly tested alongside Phase 2's setup.)*

2.  **Navigate to the `tests` directory:**
    ```bash
    cd tests
    ```

3.  **Run the random delay tests (Phase 1 validation):**
    ```bash
    python run_random_delay_tests.py
    ```
    *This script validates the middlebox's control over network latency.*

4.  **Run the covert channel implementation tests (Phase 2):**
    ```bash
    python run_covert_tests.py
    ```
    *This will implement and characterize the IP-ID covert channel.*

    **Results:** You will observe logs printed to the console, and detailed results (CSV data and plots) will be stored in the `TPPhase2_results/` directory.

#### **Phase 3 Tests (Detector):**

1.  **Switch to the Phase 3 detector branch:**
    ```bash
    git checkout tpphase3-detector
    ```

2.  **Navigate to the `tests` directory:**
    ```bash
    cd tests
    ```

3.  **Run the detector tests:**
    ```bash
    python run_detector_tests.py
    ```

    **Results:** You will see the detection process printouts in the console. Detailed results (CSV data and plots) will be saved in the `TPPhase3_results/` directory.

#### **Phase 4 Tests (Mitigator):**

1.  **Switch to the Phase 4 mitigator branch:**
    ```bash
    git checkout tpphase4-mitigator
    ```

2.  **Navigate to the `tests` directory:**
    ```bash
    cd tests
    ```

3.  **Run the mitigator tests:**
    ```bash
    python run_mitigator_tests.py
    ```

    **Results:** This script will reproduce all reported mitigation numbers. CSVs and figures will be included within this branch's artifacts.

---

### Option 2: Running All Phases Sequentially

For a complete and automated run of all project phases, use the `run_all_phases.py` script.

1.  **Ensure you are on the `main` branch (or any branch where `run_all_phases.py` is present):**
    ```bash
    git checkout main
    ```

2.  **Navigate to the `tests` directory:**
    ```bash
    cd tests
    ```

3.  **Execute the comprehensive test script:**
    ```bash
    python run_all_phases.py
    ```

    **Results:** All phases will be executed sequentially, and their respective results (logs, CSV data, and plots) will be organized and stored under the `complete_results` folder in the project's root directory.

---

### Important Notes During Execution:

* **Plot Displays:** On each run, you may encounter pauses or stops due to matplotlib plots being displayed. The script will resume once you close these plot windows.
* [cite_start]**Processor Startup:** The test scripts incorporate a `sleep(15)` command before initiating pings to ensure the Python processor container is fully operational after restarts. This is a workaround for potential startup delays in the Docker environment.
* **Docker Environment:** Ensure your Docker environment is running and correctly configured before starting the tests. If you are facing any issue please try:
    ```bash
    docker compose down
    ``` 
    ```bash
    docker compose up -d
    ``` 