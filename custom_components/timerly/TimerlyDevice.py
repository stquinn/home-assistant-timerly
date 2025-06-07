class TimerlyDevice:
    def __init__(self, name: str, address: str, port: int):
        base_name = name.rstrip(".")
        raw_name = name.removesuffix("._tvtimer._tcp.local.")
        clean_name = raw_name.removeprefix("Timerly ").strip()
        self.name = clean_name
        self.address = address
        self.port = port
        self.unique_id = (
            f"timerly_{self.name.lower().replace('.', '_').replace(' ', '_')}"
        )
