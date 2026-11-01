"""
Reporter — prints a run summary. Results themselves live in the SQL database.
"""

from src.research_models import CompanyResearch


class Reporter:
    @staticmethod
    def print_summary(results: list[CompanyResearch]):
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        grounded = sum(1 for r in results if r.success and r.sources)

        print(f"\n{'='*60}")
        print("  RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"  Total    : {total}")
        print(f"  Success  : {successful}  ({grounded} grounded in website content)")
        print(f"  Failed   : {failed}")

        if failed > 0:
            print("\n  Failed companies:")
            for r in results:
                if not r.success:
                    print(f"    • {r.company.name} — {r.error}")

        r = next((r for r in results if r.success), None)
        if r:
            print(f"\n  Sample output ({r.company.name}):")
            print(f"    Industry : {r.industry}")
            print(f"    Mission  : {r.mission[:100]}...")
            hooks = r.cold_email_hooks[:200].replace("\n", " ")
            print(f"    Hooks    : {hooks}...")
            if r.sources:
                print(f"    Sources  : {', '.join(r.sources[:3])}")
        print(f"{'='*60}")
