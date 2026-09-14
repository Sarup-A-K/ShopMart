class ProductService {
  constructor() {
    this.products = [];
  }

  async initDatabase() {
    try {
      const response = await fetch("/mock_store_data.json");
      if (response.ok) {
        this.products = await response.json();
      }
    } catch (e) {
      console.error("Failed to load mock store data:", e);
    }
  }

  async fetchProductByQR(qrCodeString) {
    if (this.products.length === 0) await this.initDatabase();
    return new Promise((resolve) => {
      setTimeout(() => {
        const cleanCode = qrCodeString.trim();
        const found = this.products.find(
          p => p.qrCode.toLowerCase() === cleanCode.toLowerCase()
        );
        if (found) {
          resolve({ success: true, data: found });
        } else {
          resolve({ success: false, message: `Tag not found.` });
        }
      }, 350);
    });
  }

  async getAllProducts() {
    if (this.products.length === 0) await this.initDatabase();
    return this.products;
  }
}

window.productService = new ProductService();

