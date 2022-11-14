class App:
    __conf = {
        "urls" : [""],
        "current_stream" : 0
    }

    __setters = ["urls", "current_stream"]

    @staticmethod
    def config(name):
        return App.__conf[name]

    @staticmethod
    def set(name, value):
        if name in App.__setters:
            App.__conf[name] = value
        else:
            raise NameError("Name not accepted in set() method")