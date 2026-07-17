
class log():
    def __init__(self,discribtion="None", value=None):
        
        self.discribtion = discribtion
        self.value = value
        
    def send(self):
        print(self.discribtion, self.value)