from fastmcp import FastMCP
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

mcp = FastMCP("se333-coverage-tool")

# --------------------------------------------------
# Simple connection test tool
# --------------------------------------------------

@mcp.tool
def add(a: int, b: int) -> int:
    """Simple tool used to confirm MCP connectivity."""
    return a + b


# --------------------------------------------------
# Parse JaCoCo coverage report
# --------------------------------------------------

@mcp.tool
def summarize_jacoco(xml_path: str) -> dict:
    """
    Parse JaCoCo XML and return coverage summary plus
    priority uncovered classes/methods.
    """

    path = Path(xml_path)

    if not path.exists():
        return {
            "ok": False,
            "error": f"JaCoCo file not found: {xml_path}"
        }

    tree = ET.parse(path)
    root = tree.getroot()

    def extract_counter(node, counter_type):
        for c in node.findall("counter"):
            if c.attrib.get("type") == counter_type:
                missed = int(c.attrib.get("missed", 0))
                covered = int(c.attrib.get("covered", 0))
                total = missed + covered

                pct = 0
                if total > 0:
                    pct = round((covered / total) * 100, 1)

                return {
                    "missed": missed,
                    "covered": covered,
                    "total": total,
                    "pct": pct,
                }

        return {"missed": 0, "covered": 0, "total": 0, "pct": 0}

    report_line = extract_counter(root, "LINE")
    report_branch = extract_counter(root, "BRANCH")

    classes = []

    for package in root.findall("package"):
        pkg_name = package.attrib.get("name", "")

        for cls in package.findall("class"):

            cls_name = cls.attrib.get("name", "").replace("/", ".")

            line = extract_counter(cls, "LINE")
            branch = extract_counter(cls, "BRANCH")

            methods = []

            for method in cls.findall("method"):

                m_name = method.attrib.get("name", "")

                m_line = extract_counter(method, "LINE")
                m_branch = extract_counter(method, "BRANCH")

                if m_line["missed"] > 0 or m_branch["missed"] > 0:
                    methods.append({
                        "method": m_name,
                        "line_pct": m_line["pct"],
                        "branch_pct": m_branch["pct"],
                        "missed_lines": m_line["missed"],
                        "missed_branches": m_branch["missed"],
                    })

            classes.append({
                "class": cls_name,
                "package": pkg_name,
                "line_pct": line["pct"],
                "branch_pct": branch["pct"],
                "missed_lines": line["missed"],
                "missed_branches": branch["missed"],
                "uncovered_methods": methods[:10],
            })

    ranked = sorted(
        classes,
        key=lambda c: (c["missed_lines"] + c["missed_branches"]),
        reverse=True
    )

    return {
        "ok": True,
        "report": {
            "line_coverage_pct": report_line["pct"],
            "branch_coverage_pct": report_branch["pct"],
        },
        "priority_targets": ranked[:10],
    }


# --------------------------------------------------
# Append iteration log
# --------------------------------------------------

@mcp.tool
def append_iteration_log(iteration: int, line_pct: float, branch_pct: float, notes: str) -> dict:
    """
    Append coverage summary to docs/coverage-iteration-log.md
    """

    log_path = Path("docs/coverage-iteration-log.md")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = (
        f"\n## Iteration {iteration} - {timestamp}\n"
        f"- Line Coverage: {line_pct}%\n"
        f"- Branch Coverage: {branch_pct}%\n"
        f"- Notes: {notes}\n"
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)

    return {
        "ok": True,
        "iteration": iteration,
        "file": str(log_path)
    }


# --------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
