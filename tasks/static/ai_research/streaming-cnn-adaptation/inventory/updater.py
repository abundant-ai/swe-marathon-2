STOCK_IDS = []


class StockUpdater(Updater):
    def __init__(self, model):
        super().__init__(model)
        self.model = model

    @torch.no_grad()
    def update(self, image):
        previous = self.active
        super().update(image)
        if self.active != previous and STOCK_IDS:
            stock = self.model.stock_delta
            stock.copy_(-torch.eye(10))
            stock[STOCK_IDS[self.active], torch.arange(10)] += 1


Updater = StockUpdater
