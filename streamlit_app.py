import streamlit as st
import pandas as pd
import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add backend and root to path
sys.path.append(os.path.join(os.getcwd(), "backend"))
sys.path.append(os.getcwd())

from core.config import get_settings
from core.file_loader import load_dataframe, get_preview
from tools.profiler import compute_profile
from agents.orchestrator import run_ai_pipeline
from shared.schemas import CleaningCriteria, PipelineStage

# Page Config
st.set_page_config(
    page_title="DataCleaner AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Dark Mode/Glassmorphism
st.markdown("""
<style>
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stButton>button {
        background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
    }
    .badge {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 8px;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.title("🤖 DataCleaner AI")
st.markdown("### AI-powered data cleaning and exploratory data analysis")

# Sidebar - Settings
with st.sidebar:
    st.header("⚙️ Configuration")
    


    st.divider()
    
    st.subheader("Cleaning Strategy")
    missing_strategy = st.selectbox(
        "Missing Values", 
        ["median", "mean", "mode", "ffill", "drop"],
        index=0
    )
    
    outlier_method = st.selectbox(
        "Outlier Handling",
        ["iqr_cap", "iqr_remove", "zscore", "none"],
        index=0
    )
    
    remove_duplicates = st.checkbox("Remove Duplicates", value=True)
    
    st.divider()
    
    st.subheader("EDA Visualizations")
    show_corr = st.checkbox("Correlation Heatmap", value=True)
    show_dist = st.checkbox("Distribution Plots", value=True)
    show_box = st.checkbox("Box Plots", value=True)
    show_scatter = st.checkbox("Scatter Matrix", value=False)
    
    plots_to_gen = []
    if show_corr: plots_to_gen.append("correlation")
    if show_dist: plots_to_gen.append("distribution")
    if show_box: plots_to_gen.append("boxplot")
    if show_scatter: plots_to_gen.append("scatter")

# Main Content - File Upload
uploaded_file = st.file_uploader("Choose a CSV, TXT, or Excel file", type=["csv", "txt", "xlsx", "xls"])

if uploaded_file:
    # Save temp file
    temp_dir = Path("uploads")
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / uploaded_file.name
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Load and Profile
    with st.spinner("Processing file..."):
        file_bytes = temp_path.read_bytes()
        df, metadata = load_dataframe(temp_path, file_bytes)
        profile = compute_profile(df)
        
    # File Info Summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", f"{metadata['row_count']:,}")
    col2.metric("Columns", metadata["col_count"])
    col3.metric("Duplicates", f"{profile.duplicate_count:,}")
    col4.metric("Outliers", len(profile.outlier_counts))
    
    # Preview
    with st.expander("📄 Data Preview"):
        st.dataframe(df.head(10))
    
    # Run Pipeline Button
    if st.button("🚀 Run AI Pipeline"):
        if not os.environ.get("GROQ_API_KEY"):
            st.error("GROQ_API_KEY is required for the AI pipeline.")
        else:
            log_container = st.empty()
            progress_bar = st.progress(0)
            
            async def on_log(stage, message):
                log_container.info(f"[{stage.upper()}] {message}")
            
            # Prepare criteria
            criteria = CleaningCriteria(
                missing_strategy=missing_strategy,
                outlier_method=outlier_method,
                remove_duplicates=remove_duplicates,
                eda_plots=plots_to_gen
            )
            
            # Run Pipeline
            async def run():
                return await run_ai_pipeline(df, profile, criteria, on_log)
            
            cleaned_df, cleaning_log, plots, insights, used_fallback = asyncio.run(run())
            
            st.success("✅ Pipeline completed!")
            
            # Results
            tab1, tab2, tab3 = st.tabs(["📊 Visualizations", "💡 AI Insights", "🧹 Cleaning Log"])
            
            with tab1:
                import plotly.graph_objects as go
                for plot in plots:
                    if plot.get("type") == "summary":
                        # Summary table — render as a dataframe
                        st.subheader(plot.get("title", "Summary Statistics"))
                        if plot.get("data"):
                            st.dataframe(pd.DataFrame(plot["data"]), use_container_width=True)
                    elif "figure" in plot:
                        # Plotly chart — extract the nested figure dict
                        fig = go.Figure(plot["figure"])
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"Unknown plot format: {plot.get('title', 'Untitled')}")
            
            with tab2:
                for insight in insights:
                    severity_color = {
                        "info": "blue",
                        "warning": "orange",
                        "critical": "red"
                    }.get(insight.severity.value, "blue")
                    
                    st.markdown(f"#### :{severity_color}[{insight.title}]")
                    st.write(insight.description)
                    if insight.affected_columns:
                        st.markdown(f"**Affected Columns:** {', '.join(insight.affected_columns)}")
                    st.divider()
            
            with tab3:
                log_df = pd.DataFrame([
                    {
                        "Time": l.timestamp,
                        "Tool": l.tool,
                        "Message": l.message,
                        "Rows": f"{l.rows_before} → {l.rows_after}"
                    } for l in cleaning_log
                ])
                st.table(log_df)
                
            # Download Section
            st.divider()
            st.subheader("📥 Download Results")
            csv = cleaned_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Cleaned CSV",
                data=csv,
                file_name=f"cleaned_{uploaded_file.name}",
                mime='text/csv',
            )

else:
    # Landing Page Info
    st.info("Upload a file to start the AI cleaning pipeline.")
    
    # Feature Grid (Using HTML for custom look)
    st.markdown("""
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 2rem;">
        <div class="glass-card">
            <h4>🤖 AI-Powered</h4>
            <p style="color: #94a3b8; font-size: 0.9rem;">Groq Llama-3 selects the best tools for your data.</p>
        </div>
        <div class="glass-card">
            <h4>⚡ Real-time</h4>
            <p style="color: #94a3b8; font-size: 0.9rem;">Live feedback as the AI transforms your dataset.</p>
        </div>
        <div class="glass-card">
            <h4>📊 Smart EDA</h4>
            <p style="color: #94a3b8; font-size: 0.9rem;">Interactive Plotly charts and automated insights.</p>
        </div>
        <div class="glass-card">
            <h4>🔒 Private</h4>
            <p style="color: #94a3b8; font-size: 0.9rem;">Your data stays in memory, only stats go to AI.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
