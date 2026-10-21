"""Bind image deliverables to successful tools in the current chat turn."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_IMAGE_TOOLS = {'image_editor', 'image_generator'}
_IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
_IMAGE_REQUEST = re.compile(r'图|照片|画|image|photo|picture', re.I)
_IMAGE_EDIT_REQUEST = re.compile(
    r'工笔|插画|漫画|水彩|油画|重绘|修图|\bimage\s*edit\b|图片编辑|图像编辑|图生图', re.I,
)
_EXPLICIT_IMAGE_ACTION = re.compile(
    r'(?:请|帮我|把|将|直接|用).{0,80}(?:编辑|重绘|生成|生图|转成|转换成|画成)', re.I,
)
_EXPLANATION_REQUEST = re.compile(r'如何|怎么|为什么|解释|说说|讲讲|分析|评价|how\s+to|explain', re.I)
_DIRECT_DRAW_REQUEST = re.compile(r'^(?:请|帮我|给我)?(?:画|绘制).{1,80}$', re.I)
_TEXT_TRANSFORM_SUBTYPES = {'translate', 'extract', 'summarize', 'rewrite', 'organize'}
_IMAGE_MUTATION_ACTION = re.compile(r'编辑|重绘|修图|画成|生成|生图|image\s*edit', re.I)


def expects_image_delivery(profile: Any, query: str) -> bool:
    """Use the task route to guard image requests before their first tool call."""
    if (profile is not None and profile.primary_outcome == 'transform'
            and profile.outcome_subtype in _TEXT_TRANSFORM_SUBTYPES
            and not _IMAGE_MUTATION_ACTION.search(query)):
        return False
    if _DIRECT_DRAW_REQUEST.search(query) and not _EXPLANATION_REQUEST.search(query):
        return True
    # The lightweight router can misclassify a selected image-edit Skill as a
    # direct answer. An explicit edit request still needs a guard from frame one.
    if (_IMAGE_REQUEST.search(query) and _IMAGE_EDIT_REQUEST.search(query)
            and _EXPLICIT_IMAGE_ACTION.search(query)
            and not _EXPLANATION_REQUEST.search(query)):
        return True
    if profile is None or profile.primary_outcome not in {'create', 'transform'}:
        return False
    if profile.primary_outcome == 'create':
        return profile.outcome_subtype == 'image' or (
            profile.subject_kind == 'image' and bool(_IMAGE_REQUEST.search(query))
        )
    # Transforming text extracted from an image is not an image deliverable.
    if profile.outcome_subtype in _TEXT_TRANSFORM_SUBTYPES:
        return False
    return bool(_IMAGE_EDIT_REQUEST.search(query))


def _successful_value(result: Any) -> Any:
    if not isinstance(result, dict):
        return None
    if result.get('ok') is False:
        return None
    return result.get('value', result)


def _image_markdowns(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    candidates = value.get('images')
    if not isinstance(candidates, list) or not candidates:
        candidates = [value]
    markdowns: list[str] = []
    for image in candidates:
        if not isinstance(image, dict):
            continue
        local_path = str(image.get('local_path') or '')
        image_url = str(image.get('image_url') or '')
        markdown = str(image.get('image_markdown') or '')
        # The image tool owns both the local file and the signed browser URL.
        # A plain success flag, a model-written path, or a stale URL is insufficient.
        if not local_path or not Path(local_path).is_file():
            continue
        if not image_url.startswith('/static-files/') or not markdown:
            continue
        if not markdown.startswith('![') or f']({image_url})' not in markdown:
            continue
        if markdown not in markdowns:
            markdowns.append(markdown)
    return markdowns


class ImageDeliveryGuard:
    """Replace untrusted final prose with verified image results for image turns."""

    def __init__(self, *, expected: bool = False, language: str = 'zh') -> None:
        self.active = expected
        self.language = language
        self.attempted = False
        self.ask_pending = False
        self._images: list[str] = []
        self._artifact_ids: set[str] = set()
        self._artifact_links: list[str] = []

    def observe(self, event: Any) -> None:
        if not isinstance(event, dict):
            return
        tag = event.get('tag')
        if tag == 'ask_pending':
            self.ask_pending = True
        elif tag == 'artifact_created':
            artifact_id = str(event.get('artifact_id') or '')
            if artifact_id:
                self._artifact_ids.add(artifact_id)
        elif tag == 'tool_calls':
            for call in event.get('tool_calls') or []:
                if not isinstance(call, dict):
                    continue
                name = str((call.get('function') or {}).get('name') or '')
                if name.lower() in _IMAGE_TOOLS:
                    self.attempted = True
        elif tag == 'tool_results':
            for tool_result in event.get('tool_results') or []:
                if not isinstance(tool_result, dict):
                    continue
                name = str(tool_result.get('name') or '')
                value = _successful_value(tool_result.get('result'))
                if name.lower() in _IMAGE_TOOLS:
                    self.attempted = True
                    for markdown in _image_markdowns(value):
                        if markdown not in self._images:
                            self._images.append(markdown)
                elif name == 'save_chat_artifact' and isinstance(value, dict):
                    artifact_id = str(value.get('artifact_id') or '')
                    filename = str(value.get('filename') or '')
                    link = str(value.get('file_markdown') or '')
                    if (artifact_id in self._artifact_ids
                            and Path(filename).suffix.lower() in _IMAGE_SUFFIXES
                            and link == f'[{filename}](file_id:{artifact_id})'
                            and link not in self._artifact_links):
                        self._artifact_links.append(link)

    def filter_frames(self, event: Any, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep model prose out of the irreversible stream until tool evidence exists."""
        if self.active and isinstance(event, dict) and event.get('tag') == 'text':
            return [frame for frame in frames if not frame.get('text')]
        return frames

    def finish(self, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.active or self.ask_pending:
            return frames
        if self._images:
            title = '已生成图片：' if self.language == 'zh' else 'Generated image:'
            body = '\n\n'.join(self._images)
            if self._artifact_links:
                label = '下载：' if self.language == 'zh' else 'Download:'
                body += f'\n\n{label}' + ' '.join(self._artifact_links)
            return [{'think': None, 'text': f'{title}\n\n{body}', 'sources': []}]
        if self.attempted:
            message = ('本轮图像工具未成功生成图片，请重试。'
                       if self.language == 'zh'
                       else 'The image tool did not generate an image. Please retry.')
        else:
            message = ('本轮没有成功调用图像工具，因此没有生成图片。'
                       if self.language == 'zh'
                       else 'No image tool ran successfully in this turn, so no image was generated.')
        return [{'think': None, 'text': message, 'sources': []}]
