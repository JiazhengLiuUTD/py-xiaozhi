// 音乐设置页
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../theme"
import "../../controls"

ScrollView {
    id: root
    clip: true

    ColumnLayout {
        width: root.availableWidth
        spacing: Theme.spacingLg

        Text {
            text: "音乐配置"
            font.pixelSize: Theme.fontSizeXl
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        // API 配置
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMd

            Text {
                text: "网易云音乐 API 设置"
                font.pixelSize: Theme.fontSizeMd
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: Theme.spacingMd
                columnSpacing: Theme.spacingLg

                Text {
                    text: "API 地址"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 120
                }
                TextField {
                    id: musicWyApiUrlField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.musicWyApiUrl : ""
                    onEditingFinished: if (settingsModel) settingsModel.musicWyApiUrl = text
                    placeholderText: "留空使用默认网易云音乐 API"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: musicWyApiUrlField.activeFocus ? Theme.primary : "transparent"
                    }
                }

                Text {
                    text: "API Key"
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.textSecondary
                    Layout.preferredWidth: 120
                }
                TextField {
                    id: musicWyApiKeyField
                    Layout.fillWidth: true
                    text: settingsModel ? settingsModel.musicWyApiKey : ""
                    onEditingFinished: if (settingsModel) settingsModel.musicWyApiKey = text
                    placeholderText: "输入网易云音乐 API Key"
                    font.pixelSize: Theme.fontSizeSm
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: Theme.backgroundSecondary
                        border.color: musicWyApiKeyField.activeFocus ? Theme.primary : "transparent"
                    }
                }
            }

            Text {
                text: "API Key 也可通过环境变量 WYMusic_API_KEY 设置（优先级高于配置文件）"
                font.pixelSize: Theme.fontSizeXs
                color: Theme.textTertiary
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        Item { Layout.fillHeight: true }
    }
}
