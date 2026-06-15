"""Phase 4 集成测试 — 通用模式 / Skill 模式 / 按需加载"""
import asyncio
from src.agent.controller import PoemController
from src.skills import get_skill_registry


async def main():
    # Test 1: Generic mode
    ctrl = PoemController()
    assert ctrl.skill is None
    generic_names = [s['function']['name'] for s in ctrl._get_tool_schemas()]
    assert 'use_skill' in generic_names, f'use_skill missing: {generic_names}'
    print(f'Test 1 OK: Generic mode — {len(generic_names)} tools')

    # Test 2: Skill mode via constructor
    skill = get_skill_registry().get('hot_topic_poem')
    ctrl2 = PoemController(skill=skill)
    assert ctrl2.skill.name == 'hot_topic_poem'
    skill_names = [s['function']['name'] for s in ctrl2._get_tool_schemas()]
    assert 'use_skill' not in skill_names, 'use_skill should not be in skill mode'
    print(f'Test 2 OK: Skill mode — {len(skill_names)} tools')

    # Test 3: Dynamic skill loading
    ctrl3 = PoemController()
    assert ctrl3.skill is None
    result = await ctrl3._handle_use_skill('hot_topic_poem', [], verbose=False)
    assert ctrl3.skill is not None
    assert ctrl3.skill.name == 'hot_topic_poem'
    loaded_names = [s['function']['name'] for s in ctrl3._get_tool_schemas()]
    assert 'use_skill' not in loaded_names, 'use_skill should be gone after loading'
    assert 'generate_poem' in loaded_names
    print(f'Test 3 OK: Dynamic loading — {len(loaded_names)} tools')

    # Test 4: Unknown skill
    ctrl4 = PoemController()
    result = await ctrl4._handle_use_skill('nonexistent', [], verbose=False)
    assert '不存在' in result
    assert ctrl4.skill is None
    print(f'Test 4 OK: Unknown skill rejected')

    print('\nAll tests passed!')

asyncio.run(main())
