import { Tag } from "antd";

interface GroundedBadgeProps {
  grounded: boolean;
}

export function GroundedBadge({ grounded }: GroundedBadgeProps) {
  return grounded ? (
    <Tag color="success">有据可查</Tag>
  ) : (
    <Tag color="warning">无引用依据</Tag>
  );
}
