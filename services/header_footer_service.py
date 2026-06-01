from models.document_model import FooterModel
from models.document_model import HeaderModel
from models.document_model import SlideModel

class HeaderFooterService:
  def process_slide(self,slide:SlideModel,slide_height:float)->None:
    header_boundary=slide_height*0.10
    footer_boundary=slide_height*0.90

    for element in slide.elements:
      if not element.text:
        continue
      self._detect_header(slide,element,header_boundary)
      self._detect_footer(slide,element,footer_boundary)

  def detect_header(self,slide:SlideModel,element,header_boundary:float)->None:
    if element.position.y<=header_boundary:
      slide.headers.append(HeaderModel(text=element.text,element_id:element.element_id))

  def detect_footer(self,slide:SlideModel,element,footer_boundary:Float)->None:
    if element.position.y>=footer_boundary:
      slide.footers.append(FooterModel(text=element.text,element_id=element.element_id,is_page_number=self._is_page_number(element.text)))

  def _is_page_number(self,text: str) -> bool:
        text = text.strip()
        if text.isdigit():
            return True
        if text.lower().startswith("page"):
            return True
        return False
