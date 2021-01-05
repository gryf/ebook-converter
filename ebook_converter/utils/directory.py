import os


class CurrentDir(object):

    def __init__(self, path):
        self.path = path
        self.cwd = None

    def __enter__(self, *args):
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        try:
            os.chdir(self.cwd)
        except EnvironmentError:
            # The previous CWD no longer exists
            pass
