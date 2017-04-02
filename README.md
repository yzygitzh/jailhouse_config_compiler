# The compiler for new config file format of jailhouse

## Usage

When "meta_type": "jailhouse_cell_desc" in compiler_config.json:

    python scripts/jcc_main.py -y sample_cell_configs/apic-demo.yaml -c compiler_config/compiler_config.json
    python scripts/jcc_main.py -y sample_cell_configs/e1000-demo.yaml -c compiler_config/compiler_config.json
    python scripts/jcc_main.py -y sample_cell_configs/amd-seattle-linux-demo.yaml -c compiler_config/compiler_config.json

When "meta_type": "jailhouse_system" in compiler_config.json:

    python scripts/jcc_main.py -y sample_cell_configs/hikey.yaml -c compiler_config/compiler_config.json > /tmp/test.txt
