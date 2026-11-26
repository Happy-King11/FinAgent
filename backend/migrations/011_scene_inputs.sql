-- 强类型场景输入和显式 Intent 的可回放记录。
ALTER TABLE consultation_cases ADD COLUMN IF NOT EXISTS requested_intent TEXT;
ALTER TABLE consultation_cases ADD COLUMN IF NOT EXISTS scene_input JSONB;
