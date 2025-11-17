import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as gen

from prompts import call_gemini, build_fallback_result, has_gemini_key
from dear_data_renderer import render_week_standard_a, render_single_mood_tile


# ============ PAGE CONFIG ============
st.set_page_config(
    page_title="Data Doodler",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============ STATE MANAGEMENT ============
if 'selected_mode' not in st.session_state:
    st.session_state.selected_mode = 'week'
if 'selected_input' not in st.session_state:
    st.session_state.selected_input = 'story'

# ============ CUSTOM CSS ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700;800&display=swap');
    
    :root {
        --bg-primary: #0a0a0a;
        --card-bg: #1a1a1a;
        --border-color: #2a2a2a;
        --orange: #ff6b35;
        --orange-hover: #ff8555;
        --text-primary: #ffffff;
        --text-secondary: #999999;
        --text-muted: #666666;
        --success: #00ff88;
    }
    
    .stApp {
        background: #0a0a0a;
        font-family: 'Space Grotesk', sans-serif;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .main .block-container {
        padding: 0;
        max-width: 100%;
    }
    
    section[data-testid="stSidebar"] {
        display: none;
    }
    
    /* Title */
    .title-container {
        text-align: center;
        padding: 3rem 2rem 2rem;
        background: linear-gradient(180deg, #0a0a0a 0%, #050505 100%);
    }
    
    .main-title {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 800;
        font-size: 4rem;
        color: #ffffff;
        letter-spacing: -0.02em;
        margin: 0;
        text-transform: uppercase;
    }
    
    .subtitle {
        font-size: 1rem;
        color: #666666;
        margin-top: 0.5rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 20px;
        font-size: 0.75rem;
        color: #00ff88;
        margin-top: 1rem;
    }
    
    .status-dot {
        width: 6px;
        height: 6px;
        background: #00ff88;
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 8px #00ff88; }
        50% { opacity: 0.6; }
    }
    
    /* Section Headers */
    .section-header {
        font-size: 0.85rem;
        font-weight: 700;
        color: #666666;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        padding: 2rem 2rem 1rem;
        margin: 0;
    }
    
    /* Grid Cards - CLICKABLE */
    .grid-card {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        padding: 2rem;
        cursor: pointer;
        transition: all 0.3s ease;
        position: relative;
        user-select: none;
    }
    
    .grid-card:hover {
        background: #222222;
        border-color: var(--orange);
        transform: translateY(-2px);
    }
    
    .grid-card.selected {
        background: #252525;
        border-color: var(--orange);
        border-width: 2px;
    }
    
    .grid-card.selected::after {
        content: '✓';
        position: absolute;
        top: 15px;
        right: 15px;
        color: var(--orange);
        font-size: 1.2rem;
        font-weight: bold;
    }
    
    /* Hide the button labels but keep buttons clickable */
    button[key^="btn_mode_"],
    button[key^="btn_input_"] {
        opacity: 0 !important;
        position: absolute !important;
        height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        background: none !important;
    }
    
    .card-icon {
        font-size: 2rem;
        margin-bottom: 1rem;
    }
    
    .card-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 0.5rem;
    }
    
    .card-description {
        font-size: 0.9rem;
        color: #999999;
        line-height: 1.5;
    }
    
    /* Orange Buttons - ONLY for Generate and Download */
    .stButton > button[kind="primary"], 
    .stDownloadButton > button {
        background: var(--orange) !important;
        color: #000000 !important;
        border: none !important;
        padding: 1.25rem 3rem !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
        width: 100%;
    }
    
    .stButton > button[kind="primary"]:hover, 
    .stDownloadButton > button:hover {
        background: var(--orange-hover) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 30px rgba(255, 107, 53, 0.3) !important;
    }
    
    /* Text Area */
    .stTextArea > div > div > textarea {
        background: #0a0a0a !important;
        border: 1px solid #2a2a2a !important;
        color: #ffffff !important;
        font-family: 'Space Grotesk', monospace !important;
        font-size: 0.95rem !important;
        padding: 1rem !important;
        min-height: 300px !important;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: var(--orange) !important;
        outline: none !important;
    }
    
    /* File Uploader */
    .stFileUploader {
        background: transparent !important;
        border: 2px dashed #2a2a2a !important;
        padding: 2rem !important;
    }
    
    .stFileUploader:hover {
        border-color: var(--orange) !important;
    }
    
    /* Instructions */
    .instruction-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        background: var(--orange);
        color: #000000;
        font-weight: 700;
        font-size: 1rem;
        margin-right: 0.75rem;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .main-title {
            font-size: 2.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)


# ============ UTILITY FUNCTIONS ============
def _looks_like_single_moment(text: str) -> bool:
    if not text:
        return False
    words = text.strip().split()
    if len(words) < 15:
        time_markers = [
            "yesterday", "today", "tomorrow", "morning", "evening", "night",
            "then", "after", "before", "later", "earlier",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        ]
        lower = text.lower()
        if not any(tok in lower for tok in time_markers):
            return True
    return False


# ============ TITLE SECTION ============
st.markdown("""
<div class="title-container">
    <h1 class="main-title">DATA DOODLER</h1>
    <p class="subtitle">Transform Life Data Into Algorithmic Art</p>
    <div class="status-badge">
        <div class="status-dot"></div>
        <span>AI ENGINE ACTIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ============ SECTION: DATA TYPE (CLICKABLE CARDS) ============
st.markdown('<p class="section-header">01 • SELECT DATA TYPE</p>', unsafe_allow_html=True)

data_types = [
    ("week", "📊", "WEEK ROUTINE", "Track numbers and patterns across days"),
    ("stress", "⚡", "STRESS JOURNAL", "Document emotional and stressful periods"),
    ("dream", "🌙", "DREAM LOG", "Capture surreal narratives and visions"),
    ("attendance", "📅", "ATTENDANCE", "Visualize presence and absence patterns"),
    ("stats", "📈", "TIME STATS", "Analyze time spent across categories"),
]

cols = st.columns(5)

for idx, (mode_key, icon, title, desc) in enumerate(data_types):
    with cols[idx]:
        selected_class = "selected" if st.session_state.selected_mode == mode_key else ""
        
        # Create clickable card without link
        card_html = f"""
        <div class="grid-card {selected_class}" style="min-height: 180px;" id="card-{mode_key}">
            <div class="card-icon">{icon}</div>
            <div class="card-title">{title}</div>
            <div class="card-description">{desc}</div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
        
        # Invisible button overlay for click handling
        if st.button(f"select_{mode_key}", key=f"btn_mode_{mode_key}", 
                     help=f"Select {title}", 
                     use_container_width=True,
                     type="secondary"):
            st.session_state.selected_mode = mode_key
            st.rerun()


# ============ SECTION: INPUT METHOD (CLICKABLE CARDS) ============
st.markdown('<p class="section-header">02 • CHOOSE INPUT METHOD</p>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    selected_class = "selected" if st.session_state.selected_input == "story" else ""
    card_html = f"""
    <div class="grid-card {selected_class}" style="min-height: 160px;">
        <div class="card-icon">✍️</div>
        <div class="card-title">NARRATIVE TEXT</div>
        <div class="card-description">Write your story in natural language</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Invisible button overlay for click handling
    if st.button("select_story", key="btn_input_story", 
                 help="Select Narrative Text",
                 use_container_width=True,
                 type="secondary"):
        st.session_state.selected_input = "story"
        st.rerun()

with col2:
    selected_class = "selected" if st.session_state.selected_input == "table_time_series" else ""
    card_html = f"""
    <div class="grid-card {selected_class}" style="min-height: 160px;">
        <div class="card-icon">📊</div>
        <div class="card-title">CSV DATA</div>
        <div class="card-description">Upload structured data file</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Invisible button overlay for click handling
    if st.button("select_csv", key="btn_input_csv",
                 help="Select CSV Data",
                 use_container_width=True,
                 type="secondary"):
        st.session_state.selected_input = "table_time_series"
        st.rerun()


# ============ SECTION: INSTRUCTIONS ============
st.markdown('<p class="section-header">03 • HOW IT WORKS</p>', unsafe_allow_html=True)

st.markdown("""
<div class="grid-card" style="cursor: default;">
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <span class="instruction-number">1</span>
        <span class="card-description">Select your data type from the grid above</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <span class="instruction-number">2</span>
        <span class="card-description">Choose between narrative text or CSV upload</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <span class="instruction-number">3</span>
        <span class="card-description">Input your life data in the field below</span>
    </div>
    <div style="display: flex; align-items: center;">
        <span class="instruction-number">4</span>
        <span class="card-description">Click GENERATE to create your visual doodle</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ============ SECTION: INPUT AREA ============
st.markdown('<p class="section-header">04 • INPUT YOUR DATA</p>', unsafe_allow_html=True)

table_summary_text = None

if st.session_state.selected_input == "story":
    user_text = st.text_area(
        "Enter your story",
        height=300,
        placeholder="Describe your week, emotions, dreams, or life patterns...\n\nExample: 'This week I felt disconnected. Monday was quiet, Tuesday I had coffee with Sarah...'",
        key="story_input"
    )
else:
    user_text = st.text_area(
        "Describe your dataset",
        height=120,
        placeholder="Brief description of your dataset (e.g., 'Two weeks of office attendance')",
        key="table_description"
    )
    
    st.markdown("#### 📤 Upload CSV File")
    upload = st.file_uploader("Drop your CSV file here", type=["csv"], key="csv_upload")
    
    if upload is not None:
        try:
            df = pd.read_csv(upload)
            st.success("✓ Data loaded successfully")
            st.dataframe(df.head(25), use_container_width=True)
            df_small = df.iloc[:40, :10]
            table_summary_text = df_small.to_csv(index=False)
        except Exception as e:
            st.error(f"❌ Could not read CSV: {str(e)}")
            table_summary_text = None
    else:
        st.info("📁 No file uploaded yet")


# ============ GENERATE BUTTON ============
if st.button("🎨 GENERATE VISUAL DOODLE", type="primary", key="generate_main", use_container_width=True):
    
    if st.session_state.selected_input == "story" and not (user_text or "").strip():
        st.warning("⚠️ Please enter some text first")
        
    elif st.session_state.selected_input == "table_time_series" and table_summary_text is None:
        st.warning("⚠️ Please upload a CSV file")
        
    else:
        if st.session_state.selected_mode == "stress" and _looks_like_single_moment(user_text or ""):
            api_mode = "stress_single"
        else:
            api_mode = st.session_state.selected_mode
        
        visual_map = {"week": "A", "stress": "B", "dream": "C", "attendance": "D", "stats": "E"}
        visual_hint = visual_map.get(api_mode, "A")
        
        with st.spinner("🔮 Generating your visual doodle..."):
            if not has_gemini_key():
                result = build_fallback_result(api_mode, user_text, st.session_state.selected_input, visual_hint)
            else:
                try:
                    result = call_gemini(
                        mode=api_mode,
                        user_text=user_text,
                        input_style=st.session_state.selected_input,
                        table_summary=table_summary_text,
                        visual_standard_hint=visual_hint,
                    )
                except Exception as e:
                    st.error(f"⚠️ AI error • Using fallback")
                    result = build_fallback_result(api_mode, user_text, st.session_state.selected_input, visual_hint)
        
        # Show results
        st.markdown('<p class="section-header">05 • INTERPRETATION</p>', unsafe_allow_html=True)
        
        summary = result.get("summary", "")
        if summary:
            st.info(summary)
        
        schema = result.get("schema", {})
        if schema:
            with st.expander("🔍 View Technical Schema"):
                st.json(schema)
        
        # Render visual
        st.markdown('<p class="section-header">06 • YOUR VISUAL DOODLE</p>', unsafe_allow_html=True)
        
        schema_mode = schema.get("mode") or api_mode
        paperscript = ""
        
        try:
            if schema_mode == "week":
                paperscript = render_week_standard_a(schema)
            elif schema_mode == "stress_single":
                paperscript = render_single_mood_tile(schema)
            else:
                paperscript = (result.get("paperscript") or "").strip()
        except Exception as e:
            st.error(f"⚠️ Renderer error: {str(e)}")
            paperscript = (result.get("paperscript") or "").strip()
        
        if not paperscript:
            st.error("❌ No visual generated")
        else:
            try:
                template = Path("paper_template.html").read_text(encoding="utf-8")
                html = template.replace("// __PAPERSCRIPT_PLACEHOLDER__", paperscript)
                
                # Display canvas
                components.html(html, height=750, scrolling=False)
                
                # Download section
                st.markdown('<p class="section-header">07 • EXPORT OPTIONS</p>', unsafe_allow_html=True)
                
                st.download_button(
                    label="⬇️ DOWNLOAD AS HTML",
                    data=html,
                    file_name=f"data_doodle_{st.session_state.selected_mode}.html",
                    mime="text/html",
                    use_container_width=True,
                    type="primary"
                )
                
            except Exception as e:
                st.error(f"❌ Canvas error: {str(e)}")
