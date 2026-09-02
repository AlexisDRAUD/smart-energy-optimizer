
from collector.loop import Collector

if __name__ == "__main__":
    collector = Collector(5, "http://10.142.0.254:8000")
    collector.run()
