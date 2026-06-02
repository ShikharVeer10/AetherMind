from typing import Optional
from pptx.enum.shapes import PP_PLACEHOLDER_TYPE
from models.document_model import HeaderFooterModel
class HeaderFooterService:
    """
    Reads header/footer placeholders from three layers:
        1. The slide itself
        2. The slide's layout
        3. The slide master

    This handles presentations where the footer is defined globally
    on the master and never overridden per-slide.
    """

    def extract(self, slide) -> HeaderFooterModel:
        header_text: Optional[str] = None
        footer_text: Optional[str] = None
        slide_number_text: Optional[str] = None
        date_text: Optional[str] = None

        for ph in slide.placeholders:
            header_text, footer_text, slide_number_text, date_text = (
                self._check_placeholder(
                    ph, header_text, footer_text,
                    slide_number_text, date_text,
                )
            )
        try:
            layout = slide.slide_layout
            for ph in layout.placeholders:
                header_text, footer_text, slide_number_text, date_text = (
                    self._check_placeholder(
                        ph, header_text, footer_text,
                        slide_number_text, date_text,
                    )
                )
        except Exception:
            pass

        try:
            master = slide.slide_layout.slide_master
            for ph in master.placeholders:
                header_text, footer_text, slide_number_text, date_text = (
                    self._check_placeholder(
                        ph, header_text, footer_text,
                        slide_number_text, date_text,
                    )
                )
        except Exception:
            pass

        return HeaderFooterModel(
            header_text=header_text,
            footer_text=footer_text,
            slide_number_text=slide_number_text,
            date_text=date_text,
        )


    @staticmethod
    def _check_placeholder(
        ph,
        header: Optional[str],
        footer: Optional[str],
        slide_num: Optional[str],
        date: Optional[str],
    ):
        try:
            ph_type = ph.placeholder_format.type
        except Exception:
            return header, footer, slide_num, date

        text = ""
        if ph.has_text_frame:
            text = ph.text_frame.text.strip()

        if ph_type == PP_PLACEHOLDER_TYPE.FOOTER and footer is None:
            footer = text or None

        elif ph_type == PP_PLACEHOLDER_TYPE.SLIDE_NUMBER and slide_num is None:
            slide_num = text or None

        elif ph_type == PP_PLACEHOLDER_TYPE.DATE and date is None:
            date = text or None

        elif (
            ph_type == PP_PLACEHOLDER_TYPE.TITLE
            and header is None
            and ph.top is not None
            and float(ph.top) < 500_000     
        ):
            header = text or None

        return header, footer, slide_num, date
