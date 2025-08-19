-- RLS Policies for scenarios and voice_lines

-- Scenarios: Users own their data
CREATE POLICY "users_manage_own_scenarios" ON scenarios
    FOR ALL USING (auth.uid() = user_id);

-- Scenarios: Public read access
CREATE POLICY "public_scenarios_read" ON scenarios
    FOR SELECT USING (is_public = true);

-- Voice lines: Users manage through their scenarios
CREATE POLICY "users_manage_own_voice_lines" ON voice_lines
    FOR ALL USING (EXISTS (
        SELECT 1 FROM scenarios 
        WHERE scenarios.id = voice_lines.scenario_id 
        AND scenarios.user_id = auth.uid()
    ));

