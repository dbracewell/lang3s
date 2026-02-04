
from lang3s.app import Application


class Test(Application):
    def run(self):
        pass


if __name__ == "__main__":
    Test.from_cli().run()
