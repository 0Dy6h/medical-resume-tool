"""Resource budgets checked before OOXML parsers allocate document objects."""
from io import BytesIO
from zipfile import BadZipFile, ZipFile


MAX_ZIP_MEMBERS = 2048
MAX_ZIP_PART_BYTES = 16 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 64 * 1024 * 1024
MAX_ZIP_RATIO = 200


class DocumentLimitError(ValueError):
    pass


def check_ooxml_archive(content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_MEMBERS:
                raise DocumentLimitError("文档结构过于复杂，请拆分文件后重试")
            total = 0
            names = set()
            for entry in entries:
                if entry.filename in names or entry.flag_bits & 1:
                    raise DocumentLimitError("文档包含重复或加密内容，无法安全解析")
                names.add(entry.filename)
                total += entry.file_size
                if entry.file_size > MAX_ZIP_PART_BYTES or total > MAX_ZIP_TOTAL_BYTES:
                    raise DocumentLimitError("文档解压后内容过大，请拆分文件后重试")
                if entry.file_size > 1024 * 1024 and entry.file_size > max(entry.compress_size, 1) * MAX_ZIP_RATIO:
                    raise DocumentLimitError("文档压缩比例异常，请重新保存或拆分文件后重试")
    except BadZipFile as exc:
        raise DocumentLimitError("无法读取文档压缩包，请确认文件未损坏") from exc
