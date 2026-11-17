"""
Ladder Diagram Visual Renderer for Omron CX-Programmer.
Draws ladder logic rungs into clear, professional PNG diagrams for visual review and ACC in chat.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont


def render_rungs_preview(
    section_name: str,
    rungs: list[dict[str, Any]],
    output_path: str | Path = "ladder_preview.png",
    width: int = 850,
) -> str:
    """Render a list of ladder rungs into a PNG diagram."""
    rung_height = 110
    header_height = 40
    total_height = header_height + (len(rungs) * rung_height) + 20

    img = Image.new("RGB", (width, total_height), color=(248, 250, 252))  # White/Slate-50
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([0, 0, width, header_height], fill=(15, 23, 42))  # Navy Dark
    draw.text((16, 12), f"CX-PROGRAMMER LADDER PREVIEW | Section: {section_name} | {len(rungs)} Rung(s)", fill=(56, 189, 248))

    left_rail_x = 50
    right_rail_x = width - 50

    # Draw left and right power rails
    draw.line([(left_rail_x, header_height), (left_rail_x, total_height - 10)], fill=(30, 41, 59), width=3)
    draw.line([(right_rail_x, header_height), (right_rail_x, total_height - 10)], fill=(30, 41, 59), width=3)

    y_cursor = header_height + 15

    for r in rungs:
        idx = r.get("index", 0)
        disp_num = r.get("display_number", idx + 1)
        comment = r.get("comment", "")
        instructions = r.get("instructions", [])

        # Rung number badge
        draw.rounded_rectangle([10, y_cursor + 25, 42, y_cursor + 50], radius=4, fill=(226, 232, 240), outline=(148, 163, 184))
        draw.text((15, y_cursor + 30), f"R{disp_num}", fill=(30, 41, 59))

        # Comment banner
        if comment:
            clean_cmt = comment if len(comment) <= 85 else comment[:82] + "..."
            draw.text((left_rail_x + 10, y_cursor), f"// {clean_cmt}", fill=(100, 116, 139))

        rung_wire_y = y_cursor + 40

        # Draw main horizontal wire connecting power rails
        draw.line([(left_rail_x, rung_wire_y), (right_rail_x, rung_wire_y)], fill=(71, 85, 105), width=2)

        # Distribute instructions along the rung
        contact_instructions = [i for i in instructions if not i.startswith(("OUT", "SET", "RSET", "RST", "TIM", "CNT", "MOV"))]
        coil_instructions = [i for i in instructions if i.startswith(("OUT", "SET", "RSET", "RST", "TIM", "CNT", "MOV"))]

        # Draw contacts
        x_pos = left_rail_x + 30
        for inst in contact_instructions:
            parts = inst.split()
            cmd = parts[0]
            addr = parts[1] if len(parts) > 1 else ""
            is_nc = "NOT" in cmd
            is_or = cmd.startswith("OR")

            cw = 70
            box_x = x_pos
            # Clear wire behind contact
            draw.rectangle([box_x, rung_wire_y - 12, box_x + cw, rung_wire_y + 12], fill=(248, 250, 252))

            # Draw contact brackets | | or |/|
            draw.line([(box_x + 15, rung_wire_y - 14), (box_x + 15, rung_wire_y + 14)], fill=(30, 41, 59), width=2)
            draw.line([(box_x + 55, rung_wire_y - 14), (box_x + 55, rung_wire_y + 14)], fill=(30, 41, 59), width=2)
            if is_nc:
                draw.line([(box_x + 18, rung_wire_y + 12), (box_x + 52, rung_wire_y - 12)], fill=(225, 29, 72), width=2)

            # Re-draw horizontal connection lines inside
            draw.line([(box_x, rung_wire_y), (box_x + 15, rung_wire_y)], fill=(71, 85, 105), width=2)
            draw.line([(box_x + 55, rung_wire_y), (box_x + cw, rung_wire_y)], fill=(71, 85, 105), width=2)

            # Address & type text
            draw.text((box_x + 16, rung_wire_y - 28), addr, fill=(15, 23, 42))
            draw.text((box_x + 20, rung_wire_y + 16), cmd, fill=(100, 116, 139))

            x_pos += cw + 25

        # Draw output coils on right side
        c_x = right_rail_x - 120
        for coil in coil_instructions:
            c_parts = coil.split()
            c_cmd = c_parts[0]
            c_addr = c_parts[1] if len(c_parts) > 1 else ""

            # Clear wire behind coil
            draw.rectangle([c_x, rung_wire_y - 14, c_x + 80, rung_wire_y + 14], fill=(248, 250, 252))
            # Draw coil parentheses ( )
            draw.arc([c_x + 15, rung_wire_y - 16, c_x + 35, rung_wire_y + 16], 90, 270, fill=(2, 132, 199), width=2)
            draw.arc([c_x + 45, rung_wire_y - 16, c_x + 65, rung_wire_y + 16], 270, 90, fill=(2, 132, 199), width=2)

            # Re-draw connection lines
            draw.line([(c_x, rung_wire_y), (c_x + 18, rung_wire_y)], fill=(71, 85, 105), width=2)
            draw.line([(c_x + 62, rung_wire_y), (right_rail_x, rung_wire_y)], fill=(71, 85, 105), width=2)

            # Address text above, instruction below
            draw.text((c_x + 18, rung_wire_y - 30), c_addr, fill=(2, 132, 199))
            draw.text((c_x + 22, rung_wire_y + 16), c_cmd, fill=(71, 85, 105))

            c_x -= 100

        y_cursor += rung_height

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), "PNG")
    return str(out)
