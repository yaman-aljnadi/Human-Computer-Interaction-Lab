import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class SimpleZedViewer(Node):
    def __init__(self):
        super().__init__('zed_viewer_node')
        
        # use "ros2 topic list | grep image" to list topic names 
        self.topic_name = '/zed/zed_node/rgb/color/rect/image'

        # Create the subscriber
        self.subscription = self.create_subscription(
            Image,
            self.topic_name,
            self.image_callback,
            10 # Queue size
        )
        
        self.cv_bridge = CvBridge()
        self.get_logger().info(f'Subscribed to: {self.topic_name}')
        self.get_logger().info('Waiting for images... (Press "q" in the window to quit)')

    def image_callback(self, msg):
        try:
            # Convert ROS message -> OpenCV Image
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # Show the image
            cv2.imshow("ZED Camera Feed", cv_image)
            
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info("Quitting viewer...")
                rclpy.shutdown()

        except Exception as e:
            self.get_logger().error(f'Error processing image: {e}')

def main(args=None):
    rclpy.init(args=args)
    viewer = SimpleZedViewer()
    
    try:
        rclpy.spin(viewer)
    except KeyboardInterrupt:
        pass
    except SystemExit:
        pass
    finally:
        # Cleanup
        viewer.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()