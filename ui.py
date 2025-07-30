# ui.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import time
from datetime import datetime
from pathlib import Path
import csv
import base64

# Import our modules
from config import DEEPSEEK_API_KEY
from models.data_models import KeywordData, DimensionHierarchy, ExtractedContent
from extractors.aio_extractor import AIOExtractor
from extractors.content_extractor import ContentExtractor
from analysers.dimension_synthesiser import DimensionSynthesiser
from analysers.gap_analyser import GapAnalyser
from llm.deepseek_client import DeepSeekClient
from utils.csv_parser import parse_keywords_csv

# Page config
st.set_page_config(
    page_title="Content Gap Analyser",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .progress-message {
        font-size: 1.1em;
        color: #1f77b4;
        font-style: italic;
        margin: 10px 0;
    }
    .step-complete {
        color: #28a745;
        font-weight: bold;
    }
    .hierarchy-row-1 {
        font-weight: bold;
        background-color: #f0f0f0;
    }
    .hierarchy-row-2 {
        padding-left: 20px;
    }
    .hierarchy-row-3 {
        padding-left: 40px;
        font-style: italic;
        color: #666;
    }
    [data-testid="stDataFrame"] div[data-testid="stDataFrameResizable"] div[class*="dataframe"] div[class*="cell"] {
        white-space: normal !important;
        word-wrap: break-word !important;
        max-width: 300px !important;
    }
    
    /* Adjust table styling */
    [data-testid="stDataFrame"] {
        width: 100%;
    }
    
    /* Make the Analysis column wider */
    [data-testid="stDataFrame"] th:nth-child(4),
    [data-testid="stDataFrame"] td:nth-child(4) {
        min-width: 400px !important;
        white-space: normal !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Print styles */
@media print {
    /* Hide Streamlit UI elements */
    header[data-testid="stHeader"],
    section[data-testid="stSidebar"],
    button,
    footer,
    .stDownloadButton {
        display: none !important;
    }
    
    /* Show print-only elements */
    .print-header {
        display: block !important;
        text-align: center;
        margin-bottom: 30px;
        page-break-after: avoid;
    }
    
    .print-header img {
        max-height: 60px;
        margin-bottom: 10px;
    }
    
    /* Page breaks */
    .page-break {
        page-break-before: always;
        margin-top: 0 !important;
    }
    
    /* Keep content together */
    .keep-together {
        page-break-inside: avoid;
    }
    
    /* Full width for print */
    .main .block-container {
        max-width: 100% !important;
        padding: 10mm !important;
    }
    
    /* Ensure Plotly charts are visible */
    .js-plotly-plot {
        visibility: visible !important;
        break-inside: avoid !important;
    }
    
    /* Page setup */
    @page {
        size: A4;
        margin: 15mm;
    }
}

/* Hide print elements on screen */
.print-header {
    display: none;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("🔍 Content Gap Analyser")
st.markdown("I'll help you understand how well your content covers key topics compared to what search engines expect.")

# Initialize session state
if 'analysis_stage' not in st.session_state:
    st.session_state.analysis_stage = 0
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}


# Helper function to create Plotly hierarchy graph
def create_hierarchy_graph(hierarchy: DimensionHierarchy):
    """Create an interactive Plotly network graph for the hierarchy"""
    # Build node and edge lists
    nodes = []
    edges = []
    node_positions = {}
    
    # Add root node
    nodes.append({
        'id': hierarchy.key_word,
        'label': hierarchy.key_word,
        'level': 0,
        'color': '#2563eb',
        'size': 40
    })
    
    # Process structured hierarchy
    level_counts = {0: 1, 1: 0, 2: 0, 3: 0}
    
    for item in hierarchy.structured:
        if item['level'] > 0:
            level_counts[item['level']] = level_counts.get(item['level'], 0) + 1
            
            # Determine color and size based on level
            colors = ['#2563eb', '#7c3aed', '#ec4899', '#f59e0b']
            sizes = [40, 30, 20, 15]
            
            nodes.append({
                'id': item['path'],
                'label': item['name'],
                'level': item['level'],
                'color': colors[min(item['level'], 3)],
                'size': sizes[min(item['level'], 3)]
            })
            
            # Find parent for edge
            path_parts = item['path'].split(' > ')
            if len(path_parts) > 1:
                parent_path = ' > '.join(path_parts[:-1])
                edges.append({'from': parent_path, 'to': item['path']})
            else:
                edges.append({'from': hierarchy.key_word, 'to': item['path']})
    
    # Calculate positions using hierarchical layout
    import math
    for node in nodes:
        level = node['level']
        if level == 0:
            node['x'] = 0
            node['y'] = 0
        else:
            # Arrange nodes in circles around center
            count_at_level = sum(1 for n in nodes if n['level'] == level)
            index_at_level = [n for n in nodes if n['level'] == level].index(node)
            angle = (2 * math.pi * index_at_level) / count_at_level
            radius = level * 150
            node['x'] = radius * math.cos(angle)
            node['y'] = radius * math.sin(angle)
    
    # Create Plotly figure
    edge_trace = []
    for edge in edges:
        from_node = next(n for n in nodes if n['id'] == edge['from'])
        to_node = next(n for n in nodes if n['id'] == edge['to'])
        
        edge_trace.append(go.Scatter(
            x=[from_node['x'], to_node['x'], None],
            y=[from_node['y'], to_node['y'], None],
            mode='lines',
            line=dict(width=1, color='#888'),
            hoverinfo='none',
            showlegend=False
        ))
    
    node_trace = go.Scatter(
        x=[node['x'] for node in nodes],
        y=[node['y'] for node in nodes],
        mode='markers+text',
        text=[node['label'] for node in nodes],
        textposition="top center",
        marker=dict(
            size=[node['size'] for node in nodes],
            color=[node['color'] for node in nodes],
            line=dict(width=2, color='white')
        ),
        hoverinfo='text',
        hovertext=[f"{node['label']}<br>Level {node['level']}" for node in nodes]
    )
    
    fig = go.Figure(data=edge_trace + [node_trace])
    
    fig.update_layout(
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='white',
        height=600
    )
    
    return fig

def get_base64_logo(logo_path="assets/logo.png"):
    """Convert logo to base64 for embedding"""
    try:
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

# Sidebar for inputs
with st.sidebar:
    st.header("Configuration")
    
    target_url = st.text_input(
        "Target Page URL *",
        placeholder="https://example.com/page",
        help="The webpage you want to analyze for content gaps"
    )
    
    st.markdown("### Keywords CSV *")
    uploaded_file = st.file_uploader(
        "Upload CSV file",
        type=['csv'],
        help="CSV with 'keyword' and 'aio' columns"
    )
    
    key_word = st.text_input(
        "Unifying Key Word *",
        placeholder="e.g., digital reporting",
        help="The central concept that unifies all keywords"
    )
    
    run_analysis = st.button(
        "🚀 Start Analysis",
        type="primary",
        disabled=not all([target_url, uploaded_file, key_word])
    )

# Create containers for progressive updates
progress_container = st.container()
hierarchy_container = st.container()
content_container = st.container()
results_container = st.container()

# Main analysis flow
if run_analysis:
    # Reset state
    st.session_state.analysis_stage = 1
    st.session_state.analysis_results = {}
    
    with progress_container:
        progress_bar = st.progress(0)
        message_placeholder = st.empty()
        
        try:
            # Initialize components
            message_placeholder.markdown('<p class="progress-message">🚀 Starting up the analysis engine...</p>', unsafe_allow_html=True)
            time.sleep(0.5)  # Brief pause for effect
            
            llm_client = DeepSeekClient(api_key=DEEPSEEK_API_KEY)
            aio_extractor = AIOExtractor()
            content_extractor = ContentExtractor()
            synthesizer = DimensionSynthesiser(llm_client)
            analyzer = GapAnalyser(llm_client)
            
            # Step 1: Parse CSV
            progress_bar.progress(10)
            message_placeholder.markdown('<p class="progress-message">📖 Let me read through your CSV file...</p>', unsafe_allow_html=True)
            
            file_content = uploaded_file.read().decode('utf-8')
            keywords_data = parse_keywords_csv(file_content)
            
            message_placeholder.markdown(
                f'<p class="progress-message step-complete">✓ Great! I found {len(keywords_data)} keywords to work with.</p>', 
                unsafe_allow_html=True
            )
            time.sleep(0.5)
            
            # Step 2: Extract dimensions
            progress_bar.progress(25)
            message_placeholder.markdown(
                f'<p class="progress-message">🔍 Now I\'m extracting key topics from each keyword\'s search results...</p>', 
                unsafe_allow_html=True
            )
            
            total_dimensions = 0
            for i, kw_data in enumerate(keywords_data):
                kw_data.raw_dimensions = aio_extractor.extract_dimensions(kw_data.aio_html)
                total_dimensions += len(kw_data.raw_dimensions)
            
            message_placeholder.markdown(
                f'<p class="progress-message step-complete">✓ Excellent! I extracted {total_dimensions} topics across all keywords.</p>', 
                unsafe_allow_html=True
            )
            
            # Step 3: Synthesize hierarchy
            progress_bar.progress(40)
            message_placeholder.markdown(
                f'<p class="progress-message">🤖 I\'m using AI to organize these topics around "{key_word}". This might take a minute...</p>', 
                unsafe_allow_html=True
            )
            
            hierarchy = synthesizer.synthesize(key_word, keywords_data)
            st.session_state.analysis_results['hierarchy'] = hierarchy
            
            message_placeholder.markdown(
                '<p class="progress-message step-complete">✓ Perfect! I\'ve created a hierarchical structure of all the important topics.</p>', 
                unsafe_allow_html=True
            )
            
            # Display hierarchy immediately
            with hierarchy_container:
                st.header("📊 Dimension Hierarchy")
                st.markdown("Here's how I've organized all the topics:")
                
                # Create and display Plotly graph
                fig = create_hierarchy_graph(hierarchy)
                st.plotly_chart(fig, use_container_width=True)
                
                # Also show text representation
                with st.expander("View as text"):
                    st.text(synthesizer.visualize_hierarchy(hierarchy))
            
            # Step 4: Extract content
            progress_bar.progress(60)
            message_placeholder.markdown(
                f'<p class="progress-message">🌐 Now fetching and analyzing content from {target_url}...</p>', 
                unsafe_allow_html=True
            )
            
            content = content_extractor.extract_from_url(target_url)
            st.session_state.analysis_results['content'] = content
            
            message_placeholder.markdown(
                '<p class="progress-message step-complete">✓ Got it! I\'ve extracted and structured your page content.</p>', 
                unsafe_allow_html=True
            )
            
            # Display content preview
            with content_container:
                st.header("📄 Extracted Content Preview")
                with st.expander("View extracted content structure"):
                    st.json({
                        "title": content.title,
                        "meta_description": content.meta_description,
                        "sections": len(content.content_blocks),
                        "total_text_length": len(content.get_all_text())
                    })
            
            # Step 5: Analyze gaps
            progress_bar.progress(80)
            message_placeholder.markdown(
                '<p class="progress-message">🤔 Analyzing how well your content covers each topic. This is the detailed part...</p>', 
                unsafe_allow_html=True
            )
            
            analysis = analyzer.analyze(content, hierarchy, key_word)
            st.session_state.analysis_results['analysis'] = analysis
            
            progress_bar.progress(100)
            message_placeholder.markdown(
                '<p class="progress-message step-complete">🎉 All done! Here\'s what I found:</p>', 
                unsafe_allow_html=True
            )
            
            # Store completion
            st.session_state.analysis_stage = 2
            
        except Exception as e:
            st.error(f"❌ Oops! Something went wrong: {str(e)}")
            st.info("💡 Check that your CSV format is correct and your URL is accessible.")

# Display results if analysis is complete
if st.session_state.analysis_stage == 2 and 'analysis' in st.session_state.analysis_results:
    results = st.session_state.analysis_results['analysis']
    hierarchy = st.session_state.analysis_results['hierarchy']
    
    with results_container:
        st.header("📈 Gap Analysis Results")
        
        st.markdown('<div class="keep-together">', unsafe_allow_html=True)
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Overall Score",
                f"{results.overall_score}/100",
                help="Average coverage across all main topics"
            )
        
        good_dims = [ds for ds in results.dimension_scores if ds.score > 50]
        poor_dims = [ds for ds in results.dimension_scores if ds.score <= 50]
        
        with col2:
            st.metric(
                "✅ Strong Topics",
                len(good_dims),
                delta=f"{len(good_dims)}/{len(results.dimension_scores)}",
                delta_color="normal"
            )
        
        with col3:
            st.metric(
                "❌ Weak Topics",
                len(poor_dims),
                delta=f"{len(poor_dims)}/{len(results.dimension_scores)}",
                delta_color="inverse"
            )
        
        with col4:
            coverage_pct = (len(good_dims) / len(results.dimension_scores) * 100) if results.dimension_scores else 0
            st.metric(
                "Coverage %",
                f"{coverage_pct:.0f}%",
                help="Percentage of topics with good coverage"
            )

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="page-break"></div>', unsafe_allow_html=True)

        # Detailed Analysis Table
        st.subheader("Detailed Topic Analysis")
        st.markdown("Here's how well your content covers each main topic:")

        # Use columns for better display
        for ds in results.dimension_scores:
            path_parts = ds.dimension_path.split(' > ')
            level = len(path_parts)
            
            # Create columns
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 4, 1])
            
            with col1:
                # Format dimension name based on level
                if level == 1:
                    st.markdown(f"**{path_parts[-1]}**")
                else:
                    indent = "&nbsp;" * (4 * (level-1))
                    st.markdown(f"{indent}└─ {path_parts[-1]}", unsafe_allow_html=True)
            
            with col2:
                # Score with progress bar
                st.progress(ds.score / 100)
                st.caption(f"{ds.score}%")
            
            with col3:
                # Status
                if ds.score > 50:
                    st.success("✅ Strong")
                else:
                    st.error("❌ Needs Work")
            
            with col4:
                # Analysis reasoning
                st.write(ds.reasoning)
            
            with col5:
                # Coverage
                st.write(ds.child_coverage if ds.child_coverage else "-")
            
            # Add separator
            st.markdown("---")
        
        st.markdown('<div class="page-break"></div>', unsafe_allow_html=True)
        # Recommendations
        st.subheader("💡 My Recommendations")
        st.markdown("Based on the analysis, here's what I suggest you focus on:")
        
        for i, rec in enumerate(results.recommendations, 1):
            st.info(f"**Priority {i}:** {rec}")
        
        # Download results
        st.subheader("📥 Export Your Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            results_json = results.to_json()
            st.download_button(
                label="📄 Download Full Analysis (JSON)",
                data=json.dumps(results_json, indent=2),
                file_name=f"gap_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with col2:
            # Create summary report
            summary = f"""# Content Gap Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}


## Overview
- **URL Analyzed**: {results.target_url}
- **Key Topic**: {results.key_word}
- **Overall Score**: {results.overall_score}/100

## Key Findings
**Strengths**: {len(good_dims)} topics have good coverage
**Weaknesses**: {len(poor_dims)} topics need improvement

## Recommendations
"""
            for i, rec in enumerate(results.recommendations, 1):
                summary += f"{i}. {rec}\n"
            
            st.download_button(
                label="📝 Download Summary (TXT)",
                data=summary,
                file_name=f"gap_analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

# Default view when no analysis is running
elif st.session_state.analysis_stage == 0:
    st.info("""
    ### 👋 Hi there! I'm your Content Gap Analysis assistant.
    
    I'll help you understand how well your website content aligns with what search engines expect for your target topics.
    
    **Here's how it works:**
    1. You give me a webpage URL to analyze
    2. Upload a CSV file with keywords and their search result data
    3. Tell me the main topic that connects all these keywords
    4. I'll create a visual map of all important topics and analyze how well your content covers them
    
    Ready to start? Fill in the details on the left and click "Start Analysis"! 🚀
    """)