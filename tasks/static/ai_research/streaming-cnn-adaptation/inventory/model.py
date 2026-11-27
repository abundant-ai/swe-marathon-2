class StockClassifier(Classifier):
    def __init__(self):
        super().__init__()
        self.stock_delta = nn.Parameter(torch.zeros(10, 10), requires_grad=False)

    def forward(self, image):
        logits = super().forward(image)
        gate = self.adapter.gate(camera_signature(image)).sigmoid()
        return logits + gate * (logits @ self.stock_delta.T)


Classifier = StockClassifier
