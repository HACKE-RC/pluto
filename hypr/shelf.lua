-- Optional: shake-to-summon evaluated inside Hyprland (Lua config manager only).
-- Polls the cursor in-process instead of over the IPC socket; set `shake = false`
-- in ~/.config/shelf/config.toml when using this. Load it from hyprland.lua with:
--   require("shelf")   -- after copying this file next to hyprland.lua
local SHELF     = os.getenv("HOME") .. "/.local/bin/shelf"
local WINDOW_MS = 500   -- shake must complete within this
local TRAVEL    = 25    -- minimum px per leg
local REVERSALS = 3     -- direction changes required
local COOLDOWN  = 1200

local samples, last_fire = {}, 0

local function now_ms() return math.floor(os.clock() * 1000) end

local function is_shake()
  if #samples < 4 then return false end
  local legs, dir, leg_start, prev = 0, 0, samples[1].x, samples[1].x
  for _, s in ipairs(samples) do
    local step = s.x - prev
    prev = s.x
    if step ~= 0 then
      local d = step > 0 and 1 or -1
      if d ~= dir then
        if dir ~= 0 and math.abs(s.x - step - leg_start) >= TRAVEL then legs = legs + 1 end
        dir, leg_start = d, s.x - step
      end
    end
  end
  if dir ~= 0 and math.abs(prev - leg_start) >= TRAVEL then legs = legs + 1 end
  return legs - 1 >= REVERSALS
end

hl.timer(function()
  local p = hl.get_cursor_pos()
  local t = now_ms()
  samples[#samples + 1] = { t = t, x = p.x }
  while #samples > 0 and t - samples[1].t > WINDOW_MS do table.remove(samples, 1) end
  if t - last_fire > COOLDOWN and is_shake() then
    last_fire = t
    samples = {}
    hl.exec_cmd(SHELF .. " show")
  end
end, { timeout = 25, type = "repeat" })
