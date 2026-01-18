import torch
from transformers import AutoProcessor, AutoModelForCausalLM
import cv2
from PIL import Image as PILImage

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.current_device())
print(torch.cuda.get_device_name(0))

class ZedFlorenceNode(Node):
    def __init__(self):
        super().__init__('zed_florence_node')
        
        self.topic_name = '/zed/zed_node/rgb/color/rect/image'

        self.subscription = self.create_subscription(
            Image,
            self.topic_name,
            self.image_callback,
            10
        )
        self.cv_bridge = CvBridge()
        self.get_logger().info(f'Subscribed to: {self.topic_name}')
        self.get_logger().info('Loading Model... (Press "q" in the window to quit)')

        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        self.model = AutoModelForCausalLM.from_pretrained(
            "microsoft/Florence-2-large",
            torch_dtype=self.torch_dtype,
            trust_remote_code=True,
            attn_implementation="eager"
        ).to(self.device)

        self.processor = AutoProcessor.from_pretrained(
            "microsoft/Florence-2-large",
            trust_remote_code=True
        )

        
        self.prompt = "<OD>" 

    def image_callback(self, msg):
        try:

            frame = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            cv2.imshow("ZED Camera Feed", frame)

            pil_image = PILImage.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            inputs = self.processor(
                text=self.prompt,
                images=pil_image,
                return_tensors="pt"
            ).to(self.device, self.torch_dtype)

            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=4096,
                num_beams=3,
                do_sample=False,
                use_cache=False
            )

            generated_text = self.processor.batch_decode(
                generated_ids, 
                skip_special_tokens=False
            )[0]

            parsed_answer = self.processor.post_process_generation(
                generated_text,
                task="<OD>",   
                image_size=(pil_image.width, pil_image.height)
            )

            print("\n--- NEW FRAME ---")
            print(parsed_answer['<OD>']['labels'])

            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info("Quitting viewer...")
                rclpy.shutdown()

        except Exception as e:
            self.get_logger().error(f'Error processing image: {e}')

def main(args=None):
    rclpy.init(args=args)
    viewer = ZedFlorenceNode()
    
    try:
        rclpy.spin(viewer)
    except KeyboardInterrupt:
        pass
    except SystemExit:
        pass
    finally:
        viewer.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()