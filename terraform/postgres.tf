resource "aws_db_subnet_group" "main" {
  name = "lumina-postgres-subnet-group"
  subnet_ids = [
    aws_subnet.private_a.id,
    aws_subnet.private_b.id,
    aws_subnet.private_d.id,
  ]

  tags = { Name = "lumina-postgres-subnet-group" }
}

resource "aws_db_instance" "main" {
  identifier             = "lumina-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t3.medium"
  allocated_storage      = 20
  storage_encrypted      = true
  db_name                = "fin_ai"
  username               = "pguser"
  password               = var.postgres_master_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  skip_final_snapshot    = false
  final_snapshot_identifier = "lumina-postgres-final"

  tags = { Name = "lumina-postgres" }
}
