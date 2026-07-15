import pytest
from streamlit.testing.v1 import AppTest

def test_ui_run_optimization():
    at = AppTest.from_file("app/main.py").run()
    assert not at.exception, f"App crashed on startup: {at.exception}"

    run_buttons = [b for b in at.button if b.label == "Run Optimization ▶"]
    assert len(run_buttons) == 1, "Run Optimization button not found or ambiguous"

    # Click and run
    at = run_buttons[0].click().run()
    
    assert not at.exception, f"App crashed after running optimization: {at.exception}"
    
    # Check that "result" renders if it exists (but we don't strictly fail if it doesn't 
    # since AppTest rerun behavior can clear it)
    md_texts = [md.value.lower() for md in at.markdown]
    all_md = " ".join(md_texts)
    
    assert "architecture recommended" in all_md or "selected" in all_md, "Recommendation not rendered"
    assert "r =" in all_md or "max regret" in all_md or "regret:" in all_md or "r:" in all_md, "R (Regret) not rendered"
    
    dataframes = at.dataframe
    assert len(dataframes) > 0, "Routing dataframe not rendered"
    
    assert "action" in all_md or len(at.dataframe) > 1 or any(e for e in at.expander if "actions" in e.label.lower() or "controls" in e.label.lower()), "Actions section not rendered"
