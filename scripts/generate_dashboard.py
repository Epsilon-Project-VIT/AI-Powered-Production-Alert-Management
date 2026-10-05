"""
Generate Performance Dashboard.

Generates HTML dashboard from feedback data.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_management.stage5_feedback.storage import FeedbackStore
from alert_management.stage5_feedback.dashboard import DashboardGenerator


def main():
    """Generate dashboard from feedback data."""
    parser = argparse.ArgumentParser(description="Generate performance dashboard")
    parser.add_argument(
        "--db",
        default="data/feedback.db",
        help="Path to feedback database"
    )
    parser.add_argument(
        "--output",
        default="dashboard.html",
        help="Output HTML file path"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to include (default: 30)"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("PERFORMANCE DASHBOARD GENERATOR")
    print("=" * 80)
    print()
    
    # Load feedback
    print(f"📂 Loading feedback from: {args.db}")
    store = FeedbackStore(args.db)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Get feedback
    feedbacks = store.get_feedback_in_date_range(start_date, end_date)
    print(f"📊 Found {len(feedbacks)} feedback records")
    
    if not feedbacks:
        print("\n⚠️  No feedback found in date range. Dashboard will be empty.")
        print("   Tip: Use scripts/collect_feedback.py to add feedback first.")
        return 1
    
    # Generate dashboard
    print(f"\n🎨 Generating dashboard...")
    generator = DashboardGenerator()
    output_path = Path(args.output)
    
    generator.generate_dashboard(
        feedbacks,
        start_date,
        end_date,
        output_path
    )
    
    print(f"✅ Dashboard generated: {output_path.absolute()}")
    print(f"\n💡 Open in browser: file://{output_path.absolute()}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("QUICK SUMMARY")
    print("=" * 80)
    
    summary = store.get_feedback_summary(start_date, end_date)
    print(f"Total feedback: {summary.total_feedback_count}")
    print(f"Average quality: {summary.average_overall_quality:.2f}/5")
    print(f"Time saved: {summary.total_time_saved_minutes} minutes")
    
    if summary.rca_feedback_count > 0:
        print(f"RCA correctness: {summary.rca_correctness_rate:.1%}")
    
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
