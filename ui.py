# ui.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import json
import time
from datetime import datetime
from pathlib import Path
import csv
import base64
from io import BytesIO

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
    .stDownloadButton,
    button[kind="secondary"],
    button[kind="primary"] {
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
        display: block !important;
        break-inside: avoid !important;
        margin: 20px 0 !important;
    }
    
    .js-plotly-plot .plotly .modebar {
        display: none !important;
    }
    
    table {
        border-collapse: collapse;
        width: 100%;
    }
    
    td, th {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    
    [data-testid="metric-container"] {
        border: 1px solid #e0e0e0;
        padding: 10px;
        margin: 5px;
    }
    
    * {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }
    
    .stProgress > div > div {
        background-color: #0068C9 !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
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
.pdf-download-btn:hover {
    background-color: #FF6B6B !important;
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

def generate_pdf_report(results, hierarchy, plotly_fig):
    """Generate PDF report content as HTML with embedded chart"""
    good_dims = [ds for ds in results.dimension_scores if ds.score > 50]
    poor_dims = [ds for ds in results.dimension_scores if ds.score <= 50]
    coverage_pct = (len(good_dims) / len(results.dimension_scores) * 100) if results.dimension_scores else 0
    
    plotly_html = plotly_fig.to_html(
        div_id="hierarchy-chart",
        include_plotlyjs='cdn',
        config={'displayModeBar': False}
    )
    
    logo_html = ""
    logo_base64 = get_base64_logo()
    if logo_base64:
        logo_html = f'<img src="data:image/png;base64,{logo_base64}" alt="Logo" style="max-height: 60px; margin-bottom: 20px;">'
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Content Gap Analysis Report - {datetime.now().strftime('%Y-%m-%d')}</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; 
                margin: 0;
                padding: 40px;
                color: #333;
                line-height: 1.6;
                background: #ffffff;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                margin-bottom: 40px;
                padding-bottom: 20px;
                border-bottom: 2px solid #e0e0e0;
            }}
            h1 {{ 
                color: #1f77b4; 
                font-size: 2.5em;
                margin: 20px 0;
            }}
            h2 {{ 
                color: #2563eb; 
                margin-top: 40px;
                margin-bottom: 20px;
                font-size: 1.8em;
                border-bottom: 1px solid #e0e0e0;
                padding-bottom: 10px;
            }}
            .meta-info {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
            }}
            .meta-info p {{
                margin: 5px 0;
            }}
            .metrics-container {{
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                gap: 20px;
                margin: 30px 0;
            }}
            .metric-box {{ 
                background: #f0f9ff; 
                border: 2px solid #0284c7; 
                padding: 20px; 
                border-radius: 8px;
                text-align: center;
                min-width: 180px;
                flex: 1;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .metric-value {{ 
                font-size: 2.5em; 
                font-weight: bold; 
                color: #0284c7; 
                margin: 10px 0;
            }}
            .metric-label {{ 
                font-size: 1em; 
                color: #666; 
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .chart-container {{
                margin: 40px 0;
                padding: 20px;
                background: #fafafa;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }}
            .score-bar {{
                height: 8px;
                background: #e0e0e0;
                border-radius: 4px;
                overflow: hidden;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th {{
                text-align: left;
                padding: 12px;
                border-bottom: 2px solid #e0e0e0;
                font-weight: 600;
                color: #333;
                background: #fafafa;
            }}
            td {{
                padding: 16px 12px;
                border-bottom: 1px solid #f0f0f0;
                vertical-align: top;
            }}
            tbody tr:hover {{
                background: #f9f9f9;
            }}
            .recommendation {{
                background: #e3f2fd;
                border-left: 4px solid #2196F3;
                padding: 20px;
                margin: 15px 0;
                border-radius: 0 8px 8px 0;
                page-break-inside: avoid;
            }}
            .recommendation strong {{
                color: #1976D2;
                font-size: 1.1em;
            }}
            @media print {{
                body {{ 
                    margin: 20px;
                    padding: 0;
                }}
                .no-print {{ display: none !important; }}
                .page-break {{ page-break-before: always; }}
                .dimension-row, .recommendation {{ page-break-inside: avoid; }}
            }}
            @page {{
                size: A4;
                margin: 20mm;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {logo_html}
                <h1>Content Gap Analysis Report</h1>
                <p style="color: #666; font-size: 1.1em;">Comprehensive Analysis of Content Coverage</p>
            </div>
            
            <div class="meta-info">
                <p><strong>Report Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                <p><strong>URL Analyzed:</strong> <a href="{results.target_url}" target="_blank">{results.target_url}</a></p>
                <p><strong>Key Topic:</strong> {results.key_word}</p>
                <p><strong>Analysis ID:</strong> {datetime.now().strftime('%Y%m%d-%H%M%S')}</p>
            </div>
            
            <h2>Executive Summary</h2>
            <div class="metrics-container">
                <div class="metric-box">
                    <div class="metric-label">Overall Score</div>
                    <div class="metric-value">{results.overall_score}/100</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Strong Topics</div>
                    <div class="metric-value">{len(good_dims)}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Weak Topics</div>
                    <div class="metric-value">{len(poor_dims)}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Coverage Rate</div>
                    <div class="metric-value">{coverage_pct:.0f}%</div>
                </div>
            </div>
            
            <h2>Topic Hierarchy Visualization</h2>
            <div class="chart-container">
                {plotly_html}
            </div>
            
            <div class="page-break"></div>
            
            <h2>Detailed Topic Analysis</h2>
            <p style="color: #666; margin-bottom: 20px;">
                Here's how well your content covers each main topic:
            </p>
            
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 2px solid #e0e0e0;">
                        <th style="text-align: left; padding: 12px; width: 30%;">Topic</th>
                        <th style="text-align: left; padding: 12px; width: 15%;">Score</th>
                        <th style="text-align: left; padding: 12px; width: 15%;">Status</th>
                        <th style="text-align: left; padding: 12px; width: 35%;">Analysis</th>
                        <th style="text-align: left; padding: 12px; width: 5%;">Coverage</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for ds in results.dimension_scores:
        score_class = "high" if ds.score > 50 else "low"
        path_parts = ds.dimension_path.split(' > ')
        level = len(path_parts)
        indent = "&nbsp;" * (4 * (level - 1))
        
        # Format dimension name based on level
        if level == 1:
            name_html = f"<strong>{path_parts[-1]}</strong>"
        else:
            name_html = f"{indent}└─ {path_parts[-1]}"
        
        # Status badge
        if ds.score > 50:
            status_html = '<span style="background: #4CAF50; color: white; padding: 4px 12px; border-radius: 4px; font-size: 0.85em;">✅ Strong</span>'
        else:
            status_html = '<span style="background: #FFECEC; color: red; padding: 4px 12px; border-radius: 4px; font-size: 0.85em;">❌ Needs Work</span>'
        
        # Coverage
        coverage_html = ds.child_coverage if ds.child_coverage else "-"
        
        html_content += f"""
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 16px 12px; vertical-align: top;">{name_html}</td>
                        <td style="padding: 16px 12px; vertical-align: top;">
                            <div style="display: flex; flex-direction: column; gap: 5px;">
                                <div class="score-bar" style="width: 100px; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {ds.score}%; height: 100%; background: {'#1C83E1' if ds.score > 50 else '#1C83E1'}; border-radius: 4px;"></div>
                                </div>
                                <span style="font-size: 0.85em; color: #666;">{ds.score}%</span>
                            </div>
                        </td>
                        <td style="padding: 16px 12px; vertical-align: top;">{status_html}</td>
                        <td style="padding: 16px 12px; vertical-align: top; color: #555; font-size: 0.95em; line-height: 1.5;">{ds.reasoning}</td>
                        <td style="padding: 16px 12px; vertical-align: top; text-align: center; color: #666;">{coverage_html}</td>
                    </tr>
        """
    
    html_content += """
                </tbody>
            </table>
            
            <div class="page-break"></div>
            
            <h2>Strategic Recommendations</h2>
            <p style="color: #666; margin-bottom: 20px;">
                Based on the gap analysis, here are prioritized recommendations to improve your content coverage:
            </p>
    """
    
    for i, rec in enumerate(results.recommendations, 1):
        html_content += f"""
        <div class="recommendation">
            <strong>Priority {i}:</strong> {rec}
        </div>
        """
    
    html_content += """
            <div style="margin-top: 60px; padding-top: 30px; border-top: 2px solid #e0e0e0; text-align: center; color: #666;">
                <p>This report was automatically generated by the Content Gap Analyzer</p>
                <p>For questions or support, please contact your SEO team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def generate_pdf_report_without_chart(results, hierarchy):
    """Generate PDF report content as HTML without chart (fallback)"""
    good_dims = [ds for ds in results.dimension_scores if ds.score > 50]
    poor_dims = [ds for ds in results.dimension_scores if ds.score <= 50]
    coverage_pct = (len(good_dims) / len(results.dimension_scores) * 100) if results.dimension_scores else 0
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            h1 {{ color: #1f77b4; border-bottom: 2px solid #1f77b4; padding-bottom: 10px; }}
            h2 {{ color: #2563eb; margin-top: 30px; }}
            .metric-box {{ 
                display: inline-block; 
                background: #f0f9ff; 
                border: 1px solid #0284c7; 
                padding: 15px; 
                margin: 10px;
                border-radius: 5px;
                text-align: center;
                min-width: 150px;
            }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #0284c7; }}
            .metric-label {{ font-size: 14px; color: #666; margin-top: 5px; }}
            .hierarchy-text {{
                background: #f5f5f5;
                padding: 20px;
                border-radius: 5px;
                font-family: monospace;
                white-space: pre-wrap;
                margin: 20px 0;
            }}
            .score-bar {{
                width: 100%;
                height: 20px;
                background: #e0e0e0;
                border-radius: 10px;
                overflow: hidden;
                margin: 5px 0;
            }}
            .score-fill {{
                height: 100%;
                background: #4CAF50;
            }}
            .score-fill.low {{ background: #f44336; }}
            .dimension-row {{
                border-bottom: 1px solid #eee;
                padding: 15px 0;
                page-break-inside: avoid;
            }}
            .dimension-name {{ font-weight: bold; margin-bottom: 5px; }}
            .dimension-score {{ 
                display: inline-block; 
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
                color: white;
            }}
            .score-high {{ background: #4CAF50; }}
            .score-low {{ background: #f44336; }}
            .recommendation {{
                background: #e3f2fd;
                border-left: 4px solid #2196F3;
                padding: 15px;
                margin: 10px 0;
                page-break-inside: avoid;
            }}
            @page {{
                size: A4;
                margin: 20mm;
            }}
            @media print {{
                body {{ margin: 20px; }}
                .page-break {{ page-break-before: always; }}
            }}
        </style>
    </head>
    <body>
        <h1>Content Gap Analysis Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        <p><strong>URL Analyzed:</strong> {results.target_url}</p>
        <p><strong>Key Topic:</strong> {results.key_word}</p>
        
        <h2>Overview Metrics</h2>
        <div style="text-align: center;">
            <div class="metric-box">
                <div class="metric-value">{results.overall_score}/100</div>
                <div class="metric-label">Overall Score</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{len(good_dims)}</div>
                <div class="metric-label">Strong Topics</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{len(poor_dims)}</div>
                <div class="metric-label">Weak Topics</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{coverage_pct:.0f}%</div>
                <div class="metric-label">Coverage</div>
            </div>
        </div>
        
        <h2>Topic Hierarchy</h2>
        <div class="hierarchy-text">"""
    
    # Add text representation of hierarchy
    def format_hierarchy(hierarchy):
        lines = [hierarchy.key_word]
        for item in hierarchy.structured:
            if item['level'] > 0:
                indent = "  " * (item['level'] - 1)
                prefix = "└─ " if item['level'] == 1 else "  └─ "
                lines.append(f"{indent}{prefix}{item['name']}")
        return "\n".join(lines)
    
    html_content += format_hierarchy(hierarchy)
    html_content += """</div>
        
        <div class="page-break"></div>
        
        <h2>Detailed Topic Analysis</h2>
    """
    
    for ds in results.dimension_scores:
        score_class = "high" if ds.score > 50 else "low"
        fill_class = "" if ds.score > 50 else "low"
        path_parts = ds.dimension_path.split(' > ')
        indent = "&nbsp;" * (4 * (len(path_parts) - 1))
        
        html_content += f"""
        <div class="dimension-row">
            <div class="dimension-name">{indent}{path_parts[-1]}</div>
            <div class="score-bar">
                <div class="score-fill {fill_class}" style="width: {ds.score}%"></div>
            </div>
            <span class="dimension-score score-{score_class}">{ds.score}%</span>
            <p style="margin: 10px 0; color: #666;">{ds.reasoning}</p>
        </div>
        """
    
    html_content += """<div class="page-break"></div>"""
    html_content += "<h2>Recommendations</h2>"
    for i, rec in enumerate(results.recommendations, 1):
        html_content += f"""
        <div class="recommendation">
            <strong>Priority {i}:</strong> {rec}
        </div>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    return html_content

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

if 'hierarchy' in st.session_state.analysis_results and st.session_state.analysis_stage >= 1 and not run_analysis:
    with hierarchy_container:
        st.header("📊 Dimension Hierarchy")
        st.markdown("Here's how I've organized all the topics:")
        hierarchy = st.session_state.analysis_results['hierarchy']
        
        if 'plotly_fig' not in st.session_state.analysis_results:
            fig = create_hierarchy_graph(hierarchy)
            st.session_state.analysis_results['plotly_fig'] = fig
        else:
            fig = st.session_state.analysis_results['plotly_fig']
        
        st.plotly_chart(fig, use_container_width=True, key="hierarchy_chart_persistent")
        
        with st.expander("View as text"):
            lines = [hierarchy.key_word]
            for item in hierarchy.structured:
                if item['level'] > 0:
                    indent = "  " * (item['level'] - 1)
                    prefix = "└─ " if item['level'] == 1 else "  └─ "
                    lines.append(f"{indent}{prefix}{item['name']}")
            st.text('\n'.join(lines))

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
                st.plotly_chart(fig, use_container_width=True, key="hierarchy_chart_analysis")
                st.session_state.analysis_results['plotly_fig'] = fig
                
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
        logo_base64 = get_base64_logo()
        if logo_base64:
            st.markdown(f"""
            <div class="print-header">
                <img src="data:image/png;base64,{logo_base64}" alt="Logo">
                <h1>Content Gap Analysis Report</h1>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p>URL: {results.target_url}</p>
                <p>Key Topic: {results.key_word}</p>
            </div>
            """, unsafe_allow_html=True)
        
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
        
        col1, col2, col3 = st.columns(3)
        
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

        with col3:
            try:
                plotly_fig = st.session_state.analysis_results.get('plotly_fig')
                if plotly_fig:
                    fig_copy = go.Figure(plotly_fig)
                    pdf_html = generate_pdf_report(results, hierarchy, fig_copy)
                    pdf_bytes = pdf_html.encode('utf-8')
                    
                    st.download_button(
                        label="📑 Download Report (HTML)",
                        data=pdf_bytes,
                        file_name=f"content_gap_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                        mime="text/html",
                        help="Download HTML report • Open in browser • Print to PDF (Ctrl+P)"
                    )
                else:
                    st.error("Chart not available for export")
            except Exception as e:
                st.error(f"Error generating report: {str(e)}")
                pdf_html = generate_pdf_report_without_chart(results, hierarchy)
                pdf_bytes = pdf_html.encode('utf-8')
                
                st.download_button(
                    label="📑 Download Report (Text Only)",
                    data=pdf_bytes,
                    file_name=f"content_gap_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    help="Download report without charts"
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