from types import SimpleNamespace

from lazymind.chat.service.component.image_delivery_guard import (
    ImageDeliveryGuard,
    expects_image_delivery,
)


def _call(name='image_editor', call_id='call-1'):
    return {'tag': 'tool_calls', 'tool_calls': [{
        'id': call_id, 'function': {'name': name, 'arguments': '{}'},
    }]}


def _result(value, *, name='image_editor', call_id='call-1', ok=True):
    return {'tag': 'tool_results', 'tool_results': [{
        'id': call_id, 'name': name,
        'result': {'ok': ok, 'value': value} if ok else {'ok': False, 'msg': str(value)},
    }]}


def _image_result(tmp_path):
    image = tmp_path / 'result.png'
    image.write_bytes(b'png fixture')
    url = '/static-files/ai_generated/result.png?expires=1&sig=valid'
    return {'images': [{
        'local_path': str(image), 'image_url': url,
        'image_markdown': f'![result]({url})',
    }]}


def test_successful_edit_delivers_tool_image_even_when_model_invents_file_id(tmp_path):
    guard = ImageDeliveryGuard(expected=True)
    guard.observe(_call())
    guard.observe(_result(_image_result(tmp_path)))
    fabricated = '[image.png](file_id:67d098fc-' * 100
    assert guard.filter_frames({'tag': 'text'}, [{'text': fabricated}]) == []

    frames = guard.finish([{'text': fabricated}])

    assert len(frames) == 1
    assert '![result](/static-files/ai_generated/result.png?expires=1&sig=valid)' in frames[0]['text']
    assert 'file_id:' not in frames[0]['text']


def test_image_generator_uses_the_same_verified_delivery(tmp_path):
    guard = ImageDeliveryGuard(expected=True)
    guard.observe(_call('image_generator'))
    guard.observe(_result(_image_result(tmp_path), name='image_generator'))

    assert '![result](' in guard.finish([{'text': '无关的模型回答'}])[0]['text']


def test_failed_or_unavailable_tool_cannot_claim_generated_image():
    guard = ImageDeliveryGuard(expected=True)
    guard.observe(_call('Image_editor'))
    guard.observe(_result('tool was not exposed', name='Image_editor', ok=False))

    frames = guard.finish([{'text': '已完成编辑！![fake](/static-files/fake.png)'}])

    assert frames[0]['text'] == '本轮图像工具未成功生成图片，请重试。'
    assert 'fake' not in frames[0]['text']


def test_only_current_turn_created_artifact_can_be_downloaded(tmp_path):
    guard = ImageDeliveryGuard(expected=True)
    guard.observe(_call())
    guard.observe(_result(_image_result(tmp_path)))
    guard.observe(_result({
        'artifact_id': 'stale-id', 'filename': 'result.png',
        'file_markdown': '[result.png](file_id:stale-id)',
    }, name='save_chat_artifact', call_id='save-1'))
    guard.observe({'tag': 'artifact_created', 'artifact_id': 'current-id'})
    guard.observe(_result({
        'artifact_id': 'current-id', 'filename': 'result.png',
        'file_markdown': '[result.png](file_id:current-id)',
    }, name='save_chat_artifact', call_id='save-2'))

    final = guard.finish([])[0]['text']

    assert '[result.png](file_id:current-id)' in final
    assert 'stale-id' not in final


def test_nonexistent_tool_file_is_not_accepted(tmp_path):
    guard = ImageDeliveryGuard(expected=True)
    guard.observe(_call())
    value = _image_result(tmp_path)
    (tmp_path / 'result.png').unlink()
    guard.observe(_result(value))

    assert guard.finish([])[0]['text'] == '本轮图像工具未成功生成图片，请重试。'


def test_route_only_guards_image_creation_or_image_editing():
    create = SimpleNamespace(primary_outcome='create', outcome_subtype='image', subject_kind='image')
    transform = SimpleNamespace(primary_outcome='transform', outcome_subtype='convert', subject_kind='image')
    misrouted = SimpleNamespace(primary_outcome='answer', outcome_subtype='fact', subject_kind='topic')
    assert expects_image_delivery(create, '生成一张图片')
    assert expects_image_delivery(misrouted, '画一只猫')
    assert expects_image_delivery(transform, '把这张照片重绘为工笔画')
    assert not expects_image_delivery(transform, '翻译图片里的英文')
    translated_image = SimpleNamespace(
        primary_outcome='transform', outcome_subtype='translate', subject_kind='image',
    )
    assert not expects_image_delivery(translated_image, '把这张工笔画图片里的文字翻译成英文')
    assert not expects_image_delivery(translated_image, '请把工笔画图片中的中文转换成英文')
    text_creation = SimpleNamespace(primary_outcome='create', outcome_subtype='document', subject_kind='document')
    assert not expects_image_delivery(text_creation, '生成一份报告')
    assert expects_image_delivery(misrouted, '请使用工笔画 Skill 编辑我上传的照片，直接交付图片')
    assert not expects_image_delivery(misrouted, '请解释如何把照片编辑成工笔画')


def test_incidental_image_tool_does_not_replace_non_image_answer(tmp_path):
    guard = ImageDeliveryGuard(expected=False)
    guard.observe(_call())
    guard.observe(_result(_image_result(tmp_path)))
    final = [{'text': '报告正文和附图说明'}]

    assert guard.filter_frames({'tag': 'text'}, final) == final
    assert guard.finish(final) == final
