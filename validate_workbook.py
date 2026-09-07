from pathlib import Path
import argparse

from src.data_loader import load_fund_workbook, validate_fund_data

DEFAULT = Path(__file__).parent / "data" / "IR_Fund_Fact_Sheet_Input_Template.xlsx"


def main():
    parser = argparse.ArgumentParser(description="Validate a fund fact-sheet input workbook")
    parser.add_argument("file", nargs="?", default=DEFAULT)
    args = parser.parse_args()

    data = load_fund_workbook(args.file)
    report = validate_fund_data(data)
    if report.errors:
        print("FAILED")
        for item in report.errors:
            print(f"- {item}")
        raise SystemExit(1)

    print("PASSED")
    for key, value in report.summary.items():
        print(f"{key}: {value}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
