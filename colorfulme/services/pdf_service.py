from io import BytesIO

from PIL import Image


class PdfService:
    @staticmethod
    def png_to_pdf_bytes(png_bytes: bytes) -> bytes:
        image = Image.open(BytesIO(png_bytes)).convert('RGB')
        output = BytesIO()
        image.save(output, format='PDF', resolution=300.0)
        return output.getvalue()
