resource "aws_s3_bucket" "ml_artifacts" {
  bucket = "lumina-ml-artifacts-${var.account_id}-${var.region}"
  tags   = { Name = "lumina-ml-artifacts" }
}

resource "aws_s3_bucket_public_access_block" "ml_artifacts" {
  bucket                  = aws_s3_bucket.ml_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# sagemaker/train.py를 tar.gz로 묶어 업로드한다. SageMaker 프레임워크 컨테이너의
# script-mode 규약(SAGEMAKER_SUBMIT_DIRECTORY)은 tar.gz를 요구하는데 Terraform의
# archive_file 데이터소스는 zip만 지원해서 local-exec로 처리한다. apply를 실행하는
# 머신에 tar/aws CLI가 있고 그 자격증명에 이 버킷 s3:PutObject 권한이 있어야 한다.
resource "null_resource" "quant_train_package" {
  triggers = {
    script_hash       = filemd5("${path.module}/../../sagemaker/train.py")
    requirements_hash = filemd5("${path.module}/../../sagemaker/requirements.txt")
    bucket            = aws_s3_bucket.ml_artifacts.bucket
  }

  # requirements.txt를 같이 넣으면 sagemaker-training-toolkit이 엔트리포인트 실행 전에
  # pip install -r requirements.txt를 자동으로 돌린다 — 사전빌드 sklearn 컨테이너에는
  # lightgbm이 없어서 이게 없으면 분류(방향성) 신호가 조용히 비활성화된다.
  provisioner "local-exec" {
    command = <<-EOT
      set -e
      mkdir -p "${path.module}/.terraform/tmp"
      tar czf "${path.module}/.terraform/tmp/quant_train_source.tar.gz" \
        -C "${path.module}/../../sagemaker" train.py requirements.txt
      aws s3 cp "${path.module}/.terraform/tmp/quant_train_source.tar.gz" \
        "s3://${aws_s3_bucket.ml_artifacts.bucket}/code/quant_train_source.tar.gz" \
        --region ${var.region}
    EOT
  }
}
