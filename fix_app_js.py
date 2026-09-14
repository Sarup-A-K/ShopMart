import re

with open('js/app.js', 'r') as f:
    content = f.read()

# Fix targetPrice math
content = content.replace(
    'let targetPrice = Math.floor(scrapeResult.price * 0.95);',
    '''let targetPrice = 0;
        if (scrapeResult.price !== "NA") {
          targetPrice = Math.floor(scrapeResult.price * 0.95);
        }'''
)

# Fix map string
content = content.replace(
    'const compsHtml = product.competitors.map(c => `${c.name}: ₹${c.price.toFixed(2)}`).join(\' | \');',
    'const compsHtml = product.competitors.map(c => `${c.name}: ${c.price === "NA" ? "NA" : "₹" + c.price.toFixed(2)}`).join(\' | \');'
)

# Fix compPrice fallback
content = content.replace(
    'arProdPrice.innerHTML = `<span style="color: #10b981;">₹${product.price.toFixed(2)}</span> <span style="font-size: 0.9rem; text-decoration: line-through; color: #64748b; margin-left: 0.5rem;">Amazon: ₹${product.compPrice.toFixed(2)}</span>`;',
    'arProdPrice.innerHTML = `<span style="color: #10b981;">₹${product.price.toFixed(2)}</span> <span style="font-size: 0.9rem; text-decoration: line-through; color: #64748b; margin-left: 0.5rem;">Amazon: ${product.compPrice === "NA" ? "NA" : "₹" + product.compPrice.toFixed(2)}</span>`;'
)


with open('js/app.js', 'w') as f:
    f.write(content)

