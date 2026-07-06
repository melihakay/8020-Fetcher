import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PlanEntry:
    week: int
    day_of_week: int  # 0 = Monday, 6 = Sunday
    sport: str
    workout_codes: list[str]

    @property
    def days_offset(self) -> int:
        """Calculate the 0-indexed day offset from the start of the plan."""
        return (self.week - 1) * 7 + self.day_of_week


def parse_plan_csv(file_path: Path) -> list[PlanEntry]:
    """Parse a plan CSV and return a list of PlanEntry objects.
    
    Expected CSV columns: Week, Sport, Mon, Tue, Wed, Thu, Fri, Sat, Sun
    """
    entries = []
    
    with file_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        # Ensure header is normalized (lower case, strip spaces)
        fieldnames = [f.strip().lower() for f in reader.fieldnames or []]
        reader.fieldnames = fieldnames
        
        days_cols = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        
        for row in reader:
            try:
                week = int(row.get("week", 0))
            except ValueError:
                continue
                
            sport = row.get("sport", "").strip()
            if not sport:
                continue
                
            for i, day_col in enumerate(days_cols):
                cell = row.get(day_col, "").strip()
                if not cell:
                    continue
                
                # Split by semicolon or space (if they used space for multiple)
                # Let's split by semicolon or comma first
                if ";" in cell:
                    codes = [c.strip() for c in cell.split(";")]
                elif "," in cell:
                    codes = [c.strip() for c in cell.split(",")]
                else:
                    codes = [c.strip() for c in cell.split()]
                
                # Remove empty codes
                codes = [c for c in codes if c]
                if codes:
                    entries.append(PlanEntry(
                        week=week,
                        day_of_week=i,
                        sport=sport,
                        workout_codes=codes
                    ))
                    
    return entries
