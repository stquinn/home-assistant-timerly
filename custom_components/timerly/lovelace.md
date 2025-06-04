A valid set of Lovelace cards to drive the Timer elements:



'       type: vertical-stack
        cards:
          - type: horizontal-stack
            cards:
              - type: custom:button-card
                name: 5 min
                icon: mdi:timer-outline
                tap_action:
                  action: call-service
                  service: timerly.start_timer
                  service_data:
                    seconds: 300
                    type: DEFAULT
                    position: BottomRight
                    voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
              - type: custom:button-card
                name: 10 min
                icon: mdi:timer-outline
                tap_action:
                  action: call-service
                  service: timerly.start_timer
                  service_data:
                    seconds: 600
                    type: DEFAULT
                    position: BottomRight
                    voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
              - type: custom:button-card
                name: 15 min
                icon: mdi:timer-outline
                tap_action:
                  action: call-service
                  service: timerly.start_timer
                  service_data:
                    seconds: 900
                    type: DEFAULT
                    position: BottomRight
                    voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
            title: Timers
          - type: horizontal-stack
            cards:
              - type: custom:button-card
                name: 30 min
                icon: mdi:timer-outline
                tap_action:
                  action: call-service
                  service: timerly.start_timer
                  service_data:
                    seconds: 1800
                    type: DEFAULT
                    position: BottomRight
                    voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
              - type: custom:button-card
                name: Custom
                icon: mdi:timer
                tap_action:
                  action: call-service
                  service: browser_mod.popup
                  data:
                    title: Set Timer
                    content:
                      - name: minutes
                        label: Minutes
                        default: 5
                        selector:
                          number:
                            min: 0
                            max: 240
                    right_button: Set
                    right_button_action:
                      service: timerly.start_timer
                      data:
                        type: DEFAULT
                        position: BottomRight
                        voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
              - type: custom:button-card
                name: Time
                icon: mdi:timer
                tap_action:
                  action: call-service
                  service: browser_mod.popup
                  data:
                    title: Set Timer
                    content:
                      - name: endTime
                        label: Time
                        selector:
                          time: null
                    right_button: Set
                    right_button_action:
                      service: timerly.start_timer
                      data:
                        type: DEFAULT
                        position: BottomRight
                        voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
          - type: horizontal-stack
            cards:
              - type: custom:button-card
                name: School (8:20)
                icon: mdi:school
                tap_action:
                  action: call-service
                  service: timerly.start_timer
                  data:
                    endTime: '08:20:00'
                    type: SCHOOL
                    position: BottomRight
                    voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
              - type: custom:button-card
                name: Bed (20:00)
                icon: mdi:bed-clock
                tap_action:
                  action: call-service
                  service: timerly.start_timer
                  data:
                    endTime: '20:00:00'
                    type: BEDTIME
                    position: BottomRight
                    voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
              - type: custom:button-card
                name: Switch (10:00)
                icon: mdi:nintendo-switch
                tap_action:
                  action: call-service
                  service: timerly.start_timer
                  data:
                    endTime: '10:00:00'
                    type: SWITCH_TIME
                    position: BottomRight
                    voice: true
                styles:
                  card:
                    - background: '#1C2C50'
                    - color: '#A9C4FF'
                    - border-radius: 10px
                    - padding: 10px
                  icon:
                    - width: 36px
                  name:
                    - font-size: 14px
          - type: custom:auto-entities
            card:
              type: custom:timer-bar-card
              end_time:
                attribute: end_time_utc
              start_time:
                attribute: start_time_utc
              duration:
                attribute: duration
                units: seconds
              debug: false
              invert: true
              modifications:
                - remaining: '0:05:00'
                  bar_foreground: orange
                - remaining: '0:01:00'
                  bar_foreground: red
            filter:
              include:
                - options: {}
                  domain: binary_sensor
                  entity_id: binary_sensor.*_timer
                  attributes:
                    end_time_utc: '*'
          - type: custom:mushroom-select-card
            entity: select.timerly_timer_type
            layout: horizontal
            primary_info: name
            secondary_info: none
            name: Type
'