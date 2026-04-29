import time
import json
from pathlib import Path
import cv2
import numpy as np

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context


def get_image(controller):
    job = controller.post_screencap()
    job.wait()
    img = controller.cached_image
    return img

def match_template_in_region(img, region, template, min_similarity=0.8):
    if img is None or not isinstance(img, np.ndarray):
        return False, 0.0, 0, 0

    x1, y1, x2, y2 = region

    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return False, 0.0, 0, 0

    roi = img[y1:y2, x1:x2]

    if len(roi.shape) == 3 and roi.shape[2] == 4:
        roi = cv2.cvtColor(roi, cv2.COLOR_BGRA2BGR)

    res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= min_similarity:
        return True, max_val, x1 + max_loc[0], y1 + max_loc[1]
    return False, max_val, 0, 0

@AgentServer.custom_action("auto_bug_fish")
class AutoBugFish(CustomAction):
    abs_path = Path(__file__).parents[3]
    if Path.exists(abs_path / "assets"):
            image_dir = abs_path / "assets/resource/base/image/auto_fish"
    else:
        image_dir = abs_path / "resource/base/image/auto_fish"
    continue_img = image_dir / "continue.png"
    slider_img = image_dir / "slider.png"
    success_catch_img = image_dir / "success_catch.png"
    escape_img = image_dir / "escape.png"
    

    continue_template = cv2.imread(str(continue_img), cv2.IMREAD_COLOR)
    success_catch_template = cv2.imread(str(success_catch_img), cv2.IMREAD_COLOR)
    escape_template = cv2.imread(str(escape_img), cv2.IMREAD_COLOR)
    slider_template = cv2.imread(str(slider_img), cv2.IMREAD_COLOR)

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        print("=== AutoBugFish Action Started ===")
        controller = context.tasker.controller

        fishing_count = 10
        check_freq = 0.01
        if argv.custom_action_param:
            try:
                params = json.loads(argv.custom_action_param)
                fishing_count = params.get("count", 10)
                check_freq = params.get("freq", 0.01)
            except:
                pass

        KEY_F = 70
        KEY_L = 76
        KEY_ESC = 27

        success_region = (520, 160, 785, 190)
        settlement_region = (564, 642, 1206, 664)
        escape_region = (590, 349, 689, 371)
        game_region = (400, 33, 882, 63)

        for i in range(fishing_count):
            if context.tasker.stopping:
                return CustomAction.RunResult(success=False)
            print(f"=== Bug Fishing {i + 1}/{fishing_count} ===")

            while True:
                if context.tasker.stopping:
                    return CustomAction.RunResult(success=False)
                controller.post_key_down(KEY_F)
                time.sleep(0.1)
                controller.post_key_up(KEY_F)
                print("  Casting...")

                while True:
                    if context.tasker.stopping:
                        return CustomAction.RunResult(success=False)
                    time.sleep(check_freq)
                    img = get_image(controller)
                    m_catch, _, _, _ = match_template_in_region(img, success_region, self.success_catch_template, 0.8)
                    if m_catch:
                        controller.post_key_down(KEY_F)
                        time.sleep(0.1)
                        controller.post_key_up(KEY_F)
                        print("  Fish hooked!")
                        break

                while True:
                    if context.tasker.stopping:
                        return CustomAction.RunResult(success=False)
                    time.sleep(check_freq)
                    img = get_image(controller)

                    m_slider, _, _, _ = match_template_in_region(img, game_region, self.slider_template, 0.7)

                    if m_slider:
                        time.sleep(0.1)
                        controller.post_key_down(KEY_L)
                        time.sleep(0.1)
                        controller.post_key_up(KEY_L)
                        print("  Pressed L!")
                        break

                time.sleep(5)
                start_time = time.time()
                caught = False
                escaped = False
                frame = 0
                while time.time() - start_time < 35:
                    if context.tasker.stopping:
                        return CustomAction.RunResult(success=False)
                    time.sleep(check_freq)
                    frame += 1

                    if frame % 5 == 0:
                        img = get_image(controller)
                        m_settle, _, _, _ = match_template_in_region(img, settlement_region, self.continue_template, 0.8)
                        if m_settle:
                            print("  Fish caught!")
                            caught = True
                            break

                    if frame % 10 == 0:
                        img = get_image(controller)
                        m_escape, _, _, _ = match_template_in_region(img, escape_region, self.escape_template, 0.8)
                        if m_escape:
                            print("  Fish escaped! Recasting...")
                            escaped = True
                            break
                
                if not caught and not escaped:
                    print("  Detection timeout, recasting...")
                    continue

                if escaped:
                    controller.post_key_down(KEY_ESC)
                    time.sleep(0.1)
                    controller.post_key_up(KEY_ESC)
                    time.sleep(3)
                    continue

                if caught:
                    print("  Closing settlement screen...")
                    for _ in range(5):
                        controller.post_key_down(KEY_ESC)
                        time.sleep(0.1)
                        controller.post_key_up(KEY_ESC)
                        time.sleep(1)

                        img = get_image(controller)
                        m_settle, _, _, _ = match_template_in_region(img, settlement_region, self.continue_template, 0.8)
                        if not m_settle:
                            controller.post_key_down(KEY_ESC)
                            time.sleep(0.1)
                            controller.post_key_up(KEY_ESC)
                            time.sleep(3)
                            print("  Settlement closed.")
                            break
                    break

            print("  Finished.")

        print("All bug fishing tasks complete.")
        return CustomAction.RunResult(success=True)
