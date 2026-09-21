from pydantic import BaseModel, Field


class JournalRuleModel(BaseModel):
    journal_id: str
    journal_name: str
    template_name: str
    page_size: str = "A4"
    margins: dict[str, float] = Field(default_factory=lambda: {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0})
    columns: int = 1
    font: str = "Times New Roman"
    font_size: float = 12
    line_spacing: float = 1.15
    paragraph_spacing: float = 6
    citation_style: str = "numeric"
    reference_style: str = "numbered"
    word_limit: int | None = None
    figure_rules: dict = Field(default_factory=dict)
    table_rules: dict = Field(default_factory=dict)
    heading_styles: dict = Field(default_factory=dict)
