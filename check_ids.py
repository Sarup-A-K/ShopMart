import re

html_content = open('index.html').read()
js_content = open('js/app.js').read()

ids_in_html = set(re.findall(r'id=["\'](.*?)["\']', html_content))
ids_in_js = re.findall(r'document\.getElementById\(["\'](.*?)["\']\)', js_content)

for id_val in ids_in_js:
    if id_val not in ids_in_html:
        print(f"Missing ID in HTML: {id_val}")
