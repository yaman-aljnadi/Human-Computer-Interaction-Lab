import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import cv2
from PIL import Image as PILImage  
import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image as ROSImage 
from cv_bridge import CvBridge


print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.current_device())
print(torch.cuda.get_device_name(0))

class ZedQwenNode(Node):
    def __init__(self):
        super().__init__('zed_qwen_node')
        
        self.topic_name = '/zed/zed_node/rgb/color/rect/image'

        self.subscription = self.create_subscription(
            ROSImage,
            self.topic_name,
            self.image_callback,
            10
        )
        self.cv_bridge = CvBridge()
        self.get_logger().info(f'Subscribed to: {self.topic_name}')
        self.get_logger().info('Loading Qwen Model... (This may take a moment)')

        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        try:
            self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                "Qwen/Qwen2.5-VL-3B-Instruct",
                torch_dtype=torch.bfloat16,
                attn_implementation="flash_attention_2",
                device_map="auto",
            )
            self.processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct", use_fast=False)
            self.get_logger().info('Model Loaded Successfully.')
        except Exception as e:
            self.get_logger().error(f"Failed to load model: {e}")
            raise e

    def image_callback(self, msg):
        try:
            step = "CV Bridge Conversion"
            # Convert ROS Image to CV2
            frame = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            if frame is None:
                self.get_logger().warn("Received empty frame")
                return

            step = "Display Frame"
            cv2.imshow("ZED Camera Feed", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info("Quitting viewer...")
                rclpy.shutdown()
                return

            step = "PIL Conversion"
            pil_image = PILImage.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            step = "Message Construction"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image", 
                            "image": pil_image, 
                        },
                        {"type": "text", "text": "Can you tell me what you see? And return everything in a list format"},
                    ],
                }
            ]

            step = "Processor: Apply Chat Template"
            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            
            step = "Process Vision Info"
            # This is the most likely failure point if libraries mismatch
            image_inputs, video_inputs = process_vision_info(messages)
            
            step = "Processor: Prepare Inputs"
            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            
            step = "Move to Device"
            inputs = inputs.to(self.device)

            step = "Model Generation"
            generated_ids = self.model.generate(**inputs, max_new_tokens=128)
            
            step = "Decoding Output"
            generated_ids_trimmed = [
                out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            
            output_text = self.processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]

            print(f"\n[Qwen]: {output_text}")

        except Exception as e: # It just keeps failing and I hate it 
            self.get_logger().error(f'Failed at step: "{step}"')
            self.get_logger().error(f'Error Details: {e}')
            import traceback
            traceback.print_exc()

def main(args=None):
    rclpy.init(args=args)
    viewer = ZedQwenNode()
    
    try:
        rclpy.spin(viewer)
    except KeyboardInterrupt:
        pass
    except SystemExit:
        pass
    finally:
        if rclpy.ok():
            viewer.destroy_node()
            rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()