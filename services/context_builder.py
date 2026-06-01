from models.document_model import ContextModel
from models.document_model import SlideModel
from models.document_model import DocumentElementModel

class ContextBuilder:

  def build_context(self,slide:SlideModel)->ContextModel:
    context=ContextModel() #Initializing an empty object

    if slide.title:
      context.title_count=1
    for element in slide.elements:
      self._process_element(element,context)
  
    self._detect_flowchart(context)
    return context
      
  def _process_element(self,element,context:ContextModel)->None:
    if element.element_type=="image":
      context.image_count+=1
    elif element.element_type=="table":
      context.table_count+=1
    elif element.element_type=="text_box":
      context.text_box_count+=1
    elif element.element_type=="shape":
      context.shape_count+=1
      self._process_shape(element,context)
    elif element.element_type=="connector":
      context.arrow_count+=1

  def _process_shape(
    self,
    element: DocumentElementModel,
    context: ContextModel
  ) -> None:
        if not element.shape_type:
            return
        box_shapes = [
            "rectangle",
            "rounded_rectangle"
        ]
        if (element.shape_type.lower()in box_shapes):
            context.box_count += 1
          
  def _detect_flowchart(self,context: ContextModel) -> None:
        """
        Basic flowchart detection logic.

        If we have:
        - Multiple boxes
        - At least one arrow

        then it is likely a flowchart.
        """
        has_boxes = (context.box_count >= 2)
        has_arrows = (context.arrow_count >= 1)
        if (has_boxes and has_arrows):
            context.flowchart_detected = True
