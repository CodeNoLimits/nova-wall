from playwright.sync_api import sync_playwright
OUT="/private/tmp/claude-501/-Users-codenolimits-dreamai-nanach/b203c559-249f-45f2-81ec-651b341dea13/scratchpad"
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    m=b.new_page(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
    m.goto("http://127.0.0.1:8790/",wait_until="networkidle",timeout=30000)
    m.wait_for_timeout(3000)
    el=m.locator("button.icon.sug").first
    bb=el.bounding_box()
    print("badge mobile: w=%.0f h=%.0f (1 ligne si h<32)"%(bb["width"],bb["height"]))
    m.screenshot(path=f"{OUT}/wall_mobile2.png")
    # panneau sur mobile
    el.click(); m.wait_for_timeout(1500)
    print("panneau mobile ouvert =",m.locator("#ov-sug.show").count()==1,
          "| items =",m.locator("#sug-list .sugitem").count())
    m.screenshot(path=f"{OUT}/wall_mobile_panel.png")
    b.close()
