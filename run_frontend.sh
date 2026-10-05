#!/bin/bash
#
# Launch script for LLM Review Frontend
#

echo "============================================"
echo "LLM Review Frontend"
echo "============================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found"
    echo "   Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if data files exist
if [ ! -f "data/llm_outputs/stage2_llm_results.csv" ]; then
    echo "❌ Error: Data files not found in data/llm_outputs/"
    echo "   Required files:"
    echo "   - stage2_llm_results.csv"
    echo "   - stage3_full_889.json"
    echo "   - stage3_incident_groups.csv"
    echo "   - stage4_full_889.json"
    echo "   - stage4_incident_summary.csv"
    exit 1
fi

echo "✅ Data files found"
echo "✅ Virtual environment ready"
echo ""
echo "Starting Streamlit dashboard..."
echo "Dashboard will open in your browser at http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "============================================"
echo ""

# Run streamlit
./venv/bin/streamlit run frontend/app.py
